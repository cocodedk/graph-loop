"""Start commands and close their process groups on every ending.

Card commands run through a parent that also reaps detached descendants.
The driver holds their actual child handles until turn-end cleanup.
"""

from __future__ import annotations

import ctypes
import os
import pathlib
import signal
import subprocess
import sys
import threading
import time

owned = threading.local()  # actual child handles, held by the driver turn

GRACE_SECONDS = 5   # how long a group gets to die from SIGTERM before SIGKILL
PR_SET_PDEATHSIG = 1
_prctl = ctypes.CDLL(None, use_errno=True).prctl
"""Resolved once, at import, before any fork: the child runs this between
`setsid` and `exec`, where allocating and loading are a threaded parent's
locks to deadlock on."""


def run(argv: list[str], *, stdin: str = "", env: dict[str, str] | None = None,
        cwd: str | None = None, timeout: float,
        drop: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    """Run `argv` to completion or `timeout`, whichever comes first.

    `env` is the child's complete environment, taken exactly as
    `subprocess.Popen` takes it (`None` inherits this process's own — a
    caller that only wants to overlay a few names has already merged them
    onto its own copy before it reaches here). `drop` removes names from
    whichever environment that ends up being.

    The whole process group is killed on every return, not just `argv`'s
    direct process: on a timeout, on an interrupt, and on a plain successful
    exit, because a job the command started with `&` outlives it either way.
    On timeout `subprocess.TimeoutExpired` is re-raised carrying whatever
    output the group produced before it died — the same exception callers
    already catch from `subprocess.run`. A group that outlives even SIGKILL
    raises `OSError` instead of returning: output handed back while the
    children that produced it are still running is not a successful call.
    """
    environment = dict(env) if env is not None else (dict(os.environ) if drop else None)
    if environment is not None:
        for name in drop:
            environment.pop(name, None)
    driver = os.getpid()
    card = hasattr(owned, "processes")
    if card and owned.stopping.is_set():
        raise InterruptedError("the driver turn is closing")
    command = ([sys.executable, str(pathlib.Path(__file__).with_name("command_owner.py")),
                str(driver), *argv] if card else argv)

    def die_with_the_driver() -> None:
        """In the child, after `setsid`, before `exec`. A refusal here is a
        `SubprocessError` from `Popen`: a child the kernel will not bind to
        this driver is one nobody would ever kill, so the call fails closed
        rather than starting it. The kernel clears the request when the
        parent is ALREADY gone, so the pid is read back — a driver killed
        between the fork and this line would otherwise leave it unbound."""
        if _prctl(PR_SET_PDEATHSIG, signal.SIGTERM if card else signal.SIGKILL) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_PDEATHSIG")
        if os.getppid() != driver:
            os._exit(1)

    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, env=environment,
                          cwd=cwd, start_new_session=True,
                          # ruff PLW1509: this driver runs lanes on threads, and a
                          # callable that allocates after fork can deadlock on a
                          # lock another thread held. Accepted: it is two calls
                          # through a pointer resolved at import, and the only
                          # alternative that runs no Python in the child — exec a
                          # bootstrap interpreter in front of every gate — would
                          # change how a missing command is reported to every
                          # caller. ponytail: preexec_fn, a cgroup or an execed
                          # binary wrapper if it ever hangs a lane.
                          preexec_fn=die_with_the_driver) as proc:   # noqa: PLW1509
        if card:
            owned.processes.append(proc)
        try:
            out, err = proc.communicate(input=stdin, timeout=timeout)
            # 125 is reserved for an ownership/startup failure. A command that
            # itself returns it is conservatively treated as a harness fault.
            if card and (proc.returncode == 125 or proc.returncode < 0):
                raise OSError(f"command could not close safely: {err}")
            # The command returned, but a job it started with `&` and detached
            # these pipes from is still in its group, still able to write while
            # the caller reviews the output. Costs one `ESRCH` when there is
            # nothing left, which is the ordinary case. Inside the `try`, so a
            # Ctrl-C landing here is still the interrupt path's to finish.
            if not card and not terminate_group(proc.pid):
                raise OSError(f"{argv[0]}: the process group survived SIGKILL")
        except subprocess.TimeoutExpired:
            out, err = _kill_group(proc)
            raise subprocess.TimeoutExpired(argv, timeout, output=out, stderr=err) from None
        except BaseException:
            # Not a timeout: Ctrl-C, a broken pipe on a large prompt, anything
            # else the wait or the cleanup above can raise. `start_new_session=True` means the
            # terminal's own SIGINT never reached this group, so without this
            # an interrupted driver leaves a two-hour builder call running and
            # spending, unseen.
            if card and proc.poll() is None:
                _kill_group(proc)  # let the parent reap detached children first
            elif not card:
                _signal_group(proc.pid, signal.SIGKILL)
                group_gone(proc.pid, GRACE_SECONDS)
            raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def _kill_group(proc: subprocess.Popen) -> tuple[str, str]:
    """SIGTERM the group, then confirm every member actually left before
    handing control back — not just the direct child, whose pipes can close
    (ending `communicate`) while a background job that redirected its own
    stdio elsewhere keeps running, ignoring the same signal."""
    pgid = proc.pid
    _signal_group(pgid, signal.SIGTERM)
    try:
        out, err = proc.communicate(timeout=GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        # the direct child outlived the grace period itself: SIGKILL is the
        # only way this second, unbounded wait ever returns.
        _signal_group(pgid, signal.SIGKILL)
        out, err = proc.communicate()
    if not group_gone(pgid, GRACE_SECONDS):
        _signal_group(pgid, signal.SIGKILL)
        group_gone(pgid, GRACE_SECONDS)
    return out, err


def group_gone(pid: int, timeout: float) -> bool:
    """Poll up to `timeout` seconds for every process in `pid`'s group to
    exit. A zombie direct child still answers to `os.killpg`, so it is
    reaped here — bypassing `Popen`, which may never get a chance to reap it
    on this path — before each check; `os.killpg(pid, 0)` then raises
    `ProcessLookupError` once truly nothing is left, or `PermissionError`
    for a group this process was never allowed to ask about — either way,
    nothing more it can wait for. Exposed for `workspace_claims.kill_running`,
    which polls a group this process never forked."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass   # already reaped, by this loop or by `communicate`
        try:
            os.killpg(pid, 0)
        except (ProcessLookupError, PermissionError):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass   # already gone between the parent's timeout and this kill


def terminate_group(pgid: int, timeout: float = GRACE_SECONDS) -> bool:
    """SIGTERM a process group, wait up to `timeout` for it to be gone, then
    SIGKILL what remains. Unlike `_kill_group`, never assumes this process
    is the group's parent: `workspace_claims.kill_running` chases pgids read
    back from claims.json that it never forked. Returns whether the group
    was gone by the time this returned."""
    _signal_group(pgid, signal.SIGTERM)
    if group_gone(pgid, timeout):
        return True
    _signal_group(pgid, signal.SIGKILL)
    return group_gone(pgid, timeout)
