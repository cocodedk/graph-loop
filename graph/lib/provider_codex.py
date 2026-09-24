"""Codex as a plain text transport: the call, and nothing about what it means.

Split out of `review.py`, which asks codex for a VERDICT and calls every other
answer malformed — so a decision, which carries no verdict, came back as a
fault (astra's provider trap, section C). Two callers share this one call now:
the review decodes ACCEPT/REJECT from what it returns, the loop reads its
own closed JSON shape, and neither grades the other's answer.

`providers` imports the name back, so `from providers import codex_text` is the
door, as it is for `codex`.
"""

from __future__ import annotations

import subprocess

from providers import Outcome, _classify_text, _run


def codex_text(binary: str, prompt: str, *, model: str, effort: str,
               cwd: str = "", timeout: int = 1800, write: bool = False) -> Outcome:
    """One Codex call, read-only unless a builder opts into worktree writes.

    Through `_run`, like every other call this loop makes: the child dies with
    the driver and its seconds are recorded by the caller's own step.

    The prompt goes on stdin — a whole-source prompt as an argument blew past
    the kernel's argument limit (E2BIG) — and `cwd` is the checkout it may
    read or build, never the driver's own.

    Spend is left unset. Codex reports none, and unknown is not zero: a call
    read as free makes the campaign's spend a lie.
    """
    if write and not cwd:
        return Outcome("harness", text="a Codex build requires its worktree cwd")
    argv = [binary, "exec", "--model", model,
            "-c", f'model_reasoning_effort="{effort}"', "--sandbox",
            "workspace-write" if write else "read-only"]
    if write:
        argv += ["--ignore-user-config", "-c", 'approval_policy="never"',
                 "-c", "sandbox_workspace_write.writable_roots=[]",
                 "-c", "sandbox_workspace_write.exclude_slash_tmp=true",
                 "-c", "sandbox_workspace_write.exclude_tmpdir_env_var=true",
                 "-c", "sandbox_workspace_write.network_access=false"]
    if cwd:
        argv += ["--cd", cwd]
    argv.append("-")
    try:
        done = _run(argv, prompt, None, timeout, cwd=cwd) if write else _run(argv, prompt, None, timeout)
    except subprocess.TimeoutExpired:
        return Outcome("crash", text="the call did not return inside its timeout")
    except OSError as error:
        # The binary is not here, or cannot be run. Nothing read the question, so
        # this is the same class as a capacity or auth refusal and the belt walks
        # to its next rung — it used to raise straight out of `review.codex` and
        # kill the whole review, which is how one machine without codex installed
        # took the reviews of a whole campaign down with it (2026-09-18).
        # `capacity` is the bucket `resources.refused_before_reading` already
        # names; the text says what actually happened, because the bucket does not.
        return Outcome("capacity", text=f"{binary} could not be run here: {error}")
    blob = (done.stdout or "") + (done.stderr or "")
    if done.returncode:
        # The exit code says the call did not finish, so whatever it printed is
        # not an answer (a lesson about the harness: key on the exit code, never on
        # matched text). The words only say which kind of refusal it was.
        return Outcome(_classify_text(blob) or "crash",
                       text=(done.stdout or blob).strip()[:500], raw=blob)
    return Outcome("ok", text=done.stdout or "", raw=blob)
