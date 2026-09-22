"""Crash-recovery notes for a keep: the ref moved, but the write that marks
the card done never ran.

Split out of `keep.py` to keep it under the file's own size limit; nothing
here knows about a Keeper, only a repository path and a branch name — the
same shape as `keep_gate.py` and `keep_remote.py`.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import urllib.parse

import durable
from keep_branch import plain
from workspace_claims import say


def _quoted(branch: str) -> str:
    # Namespaced, or two branches in one repo would trip each other's notes.
    return urllib.parse.quote(plain(branch), safe="")


def note_path(repo: str, branch: str, task_id: str) -> pathlib.Path:
    return pathlib.Path(repo, ".git", f"keep-pending-{_quoted(branch)}-{task_id}")


def note(repo: str, branch: str, task_id: str, sha: str) -> pathlib.Path:
    """Write the note and put it on the platter. The caller moves the ref right
    after, and power loss between the two must not leave the branch holding a
    commit no note names — the whole reason this file exists."""
    return durable.replace(note_path(repo, branch, task_id), sha)


def pending(repo: str, branch: str) -> list[tuple[str, str]]:
    """A crash left standing: the ref moved, but the card-write that marks
    it done never ran. A note whose sha the branch does not hold is stale
    and removed here; one it DOES hold is left in place and handed back —
    the caller settles it (`settle`) only once the card is actually
    written, so a second crash in that gap finds the same note again.

    Only git's own "no" — exit 1 — makes a note stale (`git help
    git-merge-base`, and `worktree_refs.advance` reads the same call the same
    way). Any other non-zero is an error, not a verdict: the note is the one
    record that recovers this keep, so it is kept, left out of the answer —
    returned, it would mark the card done on a commit nobody proved the branch
    holds — and said on stderr, which the driver writes to `run.log`. The next
    turn asks again.
    """
    prefix = f"keep-pending-{_quoted(branch)}-"
    found: list[tuple[str, str]] = []
    for note in pathlib.Path(repo, ".git").glob(f"{prefix}*"):
        sha = note.read_text("utf-8").strip()
        ancestor = subprocess.run(
            ("git", "-C", repo, "merge-base", "--is-ancestor", sha, branch),
            capture_output=True, text=True, check=False)
        if ancestor.returncode == 0:
            found.append((note.name[len(prefix):], sha))
        elif ancestor.returncode == 1:
            note.unlink(missing_ok=True)
        else:
            say((f"keep_pending_unreadable: {note.name} stays: git could not say whether "
                  f"{branch} holds {sha[:8]}: {ancestor.stderr.strip()}"), file=sys.stderr)
    return found


def settle(repo: str, branch: str, task_id: str) -> None:
    """`task_id`'s card is written: its recovery note is no longer needed."""
    note_path(repo, branch, task_id).unlink(missing_ok=True)
