"""Pushing a campaign branch to its remote.

Split out of `keep.py` to keep it under the file's own size limit; nothing
here knows about a Keeper, only a repository path and a branch name — the
same shape as `keep_gate.py`.
"""

from __future__ import annotations

import subprocess

from keep_branch import plain


def behind(repo: str, branch: str, remote: str = "origin") -> bool:
    """True when `remote` does not contain the local branch's tip commit — a
    real "this work is not on the remote yet" state. A remote that has moved
    ahead but still contains that tip is not behind, even though its sha
    differs. Read-only, never raises: a local branch that does not exist has
    nothing to be behind on."""
    name = plain(branch)
    local = subprocess.run(("git", "-C", repo, "rev-parse", f"refs/heads/{name}"),
                           capture_output=True, text=True, check=False)
    if local.returncode:
        return False
    remote_ref = f"refs/remotes/{remote}/{name}"
    resolved = subprocess.run(("git", "-C", repo, "rev-parse", remote_ref),
                              capture_output=True, text=True, check=False)
    if resolved.returncode:
        return True
    contained = subprocess.run(
        ("git", "-C", repo, "merge-base", "--is-ancestor", local.stdout.strip(), remote_ref),
        capture_output=True, text=True, check=False)
    return contained.returncode != 0


def push(repo: str, branch: str, remote: str) -> str:
    """Push `branch` to `remote`. Never forced, never onto another branch,
    and never raises: a failed push only means the branch is not yet on the
    remote — the keep already stands, and the caller alerts instead of
    losing the task over it. The local campaign branch does not move here (only the remote-tracking ref does), so a worktree holding
    the branch is no reason to refuse: the keep that would move it under that
    checkout is refused at the ref motion instead (`keep_branch.py`)."""
    name = plain(branch)
    sent = subprocess.run(
        ("git", "-C", repo, "push", "-q", remote, f"refs/heads/{name}:refs/heads/{name}"),
        capture_output=True, text=True, check=False)
    if sent.returncode:
        return (sent.stderr.strip() or f"git push exited {sent.returncode} with no message")[-300:]
    return ""
