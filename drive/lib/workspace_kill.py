"""Finding and killing one claimed process's children and its own group.
`ClaimsMixin.kill_running` freezes the group (SIGSTOP) and calls in here for
the rest. Split out to keep workspace_claims.py under the 200-line cap: no
identity or claims-file concern lives here (that stays with
`_started`/`_verified`, next to the liveness check they mirror), so this
module never imports workspace_claims.
"""

from __future__ import annotations

import os
import pathlib
import signal

import runner


def _children_of(pid: int) -> list[int]:
    """Every pid whose parent is `pid`, from /proc — survives `runner.run`'s
    own setsid; a grandchild that calls setsid itself moves out of this reach."""
    try:
        names = os.listdir("/proc")
    except OSError:
        return []
    children = []
    for name in names:
        if not name.isdigit():
            continue
        try:
            fields = pathlib.Path(f"/proc/{name}/stat").read_text().rpartition(")")[2].split()
            if int(fields[1]) == pid:
                children.append(int(name))
        except (OSError, IndexError, ValueError):
            continue
    return children


def finish_kill(pgid: int, pid: int, signal_number: int) -> bool:
    """`pgid` is already SIGSTOPped — the caller closed the spawn race
    before calling this, so `pid`'s children are complete now. Kill every
    child's own group with the runner's TERM-wait-KILL helper, then deliver
    `signal_number` to `pgid` itself and SIGCONT it so a signal queued
    behind the freeze is actually acted on; escalate to SIGKILL if it
    survives, and wait for the group to actually be gone before returning
    — SIGKILL is delivered on the caller's behalf, not applied by it, so
    a caller that trusted the return alone could still find the group a
    zombie. `ProcessLookupError`/`PermissionError` are ignored per group —
    gone, or never ours to signal, either way nothing to do. Returns
    whether `pgid` was confirmed gone by the final poll, never merely
    whether a signal was sent: `kill_running`'s return-value contract.
    """
    for child in (_children_of(pid) if pid else ()):
        try:
            runner.terminate_group(os.getpgid(child), timeout=runner.GRACE_SECONDS)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        os.killpg(pgid, signal_number)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        os.killpg(pgid, signal.SIGCONT)
    except (ProcessLookupError, PermissionError):
        pass
    gone = runner.group_gone(pgid, runner.GRACE_SECONDS)
    if not gone:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        gone = runner.group_gone(pgid, runner.GRACE_SECONDS)
    return gone
