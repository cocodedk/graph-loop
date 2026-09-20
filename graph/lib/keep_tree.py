"""The tree a keep publishes: git itself, and the names that go into it.

Split out of `keep.py` at the file's own size limit; nothing here knows about a
Keeper, only a repository path — the same shape as `keep_gate.py` and
`keep_branch.py`. `keep.py` stays the front door.
"""

from __future__ import annotations

import os
import subprocess


def git(root: str, *args: str, check: bool = True, stdin: bytes | None = None,
        env: dict | None = None) -> str:
    # A symlink target can be arbitrary, non-UTF-8 bytes: `stdin` goes in as
    # bytes so it is never re-encoded, and only git's own stdout — always
    # ASCII here (a hex blob sha) — is decoded back to text. `env` adds to the
    # inherited environment: a keep assembles its commit in a private index.
    text = stdin is None
    done = subprocess.run(["git", "-C", root, *args], input=stdin, capture_output=True,
                          text=text, check=False,
                          env={**os.environ, **env} if env else None)
    if check and done.returncode != 0:
        stderr = done.stderr if text else done.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)}: {stderr.strip()}")
    return done.stdout if text else done.stdout.decode("ascii")


def staged_names(worktree: str) -> list[str]:
    """Every path the worktree has staged, one decoded name each.

    `--name-only` on its own C-quotes any name that is not plain ASCII, and the
    quoted text is not a path: `café.py` arrived as `"caf\\303\\251.py"`, nothing
    was there under that name, and the keep removed the file from the very commit
    that accepted it. `-z` hands the bytes over unquoted and unsplit — a newline
    in a name no longer splits one path into two either — and `os.fsdecode` is the
    decoding the filesystem itself uses, so a name that is not UTF-8 survives the
    trip back out as a git argument. (A lesson: every reader of git's paths
    reads them with `-z`.)
    """
    done = subprocess.run(("git", "-C", worktree, "diff", "--cached", "--name-only", "-z"),
                          capture_output=True, check=False)
    if done.returncode:
        raise RuntimeError("git diff --cached --name-only -z: "
                           + done.stderr.decode("utf-8", "replace").strip())
    return [os.fsdecode(name) for name in done.stdout.split(b"\0") if name]


def merged(repo: str, task_id: str, tip: str, candidate: str) -> str:
    """The tree this work makes on `tip`: a three-way merge of `candidate` — the
    task's files on the tree its worktree was cut from — with the branch as it
    stands now.

    Overlaying those files straight onto the tip is what this replaces: whatever
    another card had kept in the same file since was replaced with the older
    checkout's copy, silently, with no conflict for anyone to read (round-2
    finding 8). A merge keeps both changes when they are in different places,
    and when they are not it refuses — the branch is never published with one
    card's work quietly missing. A refused keep leaves the tree standing and the
    card for a person (`turn.py`, `lane_failed`); its work is not lost.
    """
    done = subprocess.run(("git", "-C", repo, "merge-tree", "--write-tree", tip, candidate),
                          capture_output=True, text=True, check=False)
    if done.returncode == 0:
        return done.stdout.split("\n", 1)[0].strip()   # the merged tree, then any remarks
    if done.returncode == 1:
        why = done.stdout.split("\n\n")[-1].strip()    # git's own words, after the file list
        raise RuntimeError(f"{task_id}: this work and what the branch already holds change "
                           f"the same lines — {why[:300]}")
    raise RuntimeError(f"{task_id}: the work could not be merged onto the branch tip: "
                       f"{done.stderr.strip()[:200]}")
