"""The combined-tree check: proof that a candidate commit still passes beside
whatever the branch already holds, not just alone, and the failure it raises.

Split out of `keep.py` to keep it under the file's own size limit; nothing
here knows about a Keeper, only a repository path.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

import gate_paths
from keep_failure import (  # noqa: F401 — public front door
    CombinedGateFailed,
    GateFailure,
    GateMutatedTree,
)


def _fingerprint(whole: pathlib.Path) -> str:
    """A dirty path's mode and content, never only its name.

    `provision` copies `simulation/secrets` in untracked, so a gate that
    OVERWRITES a file that was already dirty when the gates started reads as the
    same `?? …/fixture.txt` before and after, and the next gate ran on the edit
    (Codex, on the first version of this check).
    """
    try:
        mode = whole.lstat().st_mode
        if whole.is_symlink():                  # asked first: `is_file` follows the link
            digest = hashlib.sha256(os.readlink(whole).encode()).hexdigest()
        elif whole.is_file():
            with whole.open("rb") as handle:    # streamed: a gate's output may be large
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
        else:
            digest = ""                         # a directory or a socket: the mode is all there is
    except OSError:
        return "gone"                           # named by git but not here: a rename record, or removed
    return f"{mode:o}:{digest[:16]}"


def _read(checkout: str, *args: str) -> bytes:
    """git's own bytes, or the reason there is none. A call that failed is never
    read as "nothing changed": both reads would come back empty and the gate
    would be judged to have left the tree alone (`worktree_scope._git` keeps the
    same rule for the scope check)."""
    done = subprocess.run(("git", "-C", checkout, *args), capture_output=True, check=False)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {checkout}: "
                           + done.stderr.decode("utf-8", "replace").strip()[:200])
    return done.stdout


def _flags(checkout: str) -> list[str]:
    """Index entries git has been told to stop looking at.

    `--assume-unchanged` (git prints a lowercase letter) and `--skip-worktree`
    (`S`) take a tracked file out of what `git status` reports, so a gate that
    set one and then rewrote the file left the read below identical — it edited
    `a.py`, the next gate passed on the edit, and the branch was published
    without it (round-2 finding 3). A fresh checkout has none of these, so any
    one of them is itself a change.
    """
    records = (os.fsdecode(record) for record in _read(checkout, "ls-files", "-v", "-z").split(b"\0")
               if record)
    return [f"index-{record[0]} {record[2:]}" for record in records if record[0] != "H"]


def _main_line(where: str, watched: set[str]) -> list[str]:
    """Where the main line stands in `where` — the checkout the gates run in, or
    the repository itself. One line per main-line branch that exists there, so a
    gate that creates one shows up too.

    Each line carries the branch's symbolic target as well as its commit: a gate
    that turned `main` into an alias for another branch AT THE SAME COMMIT read
    identical by sha alone, so nothing refused the keep — and from then on
    whatever moved that branch moved the main line (Codex, on this read).

    `watched` is `keep_branch.protected`'s answer for the REPOSITORY, resolved
    by the caller: a clone has no remote, so asking it would lose a main line
    called `trunk`, which `origin/HEAD` is the only record of.

    The campaign branch is not read: `_publish`'s old-value guard already refuses
    a commit built on a tip that moved, and reading every branch would refuse a
    keep because a sibling campaign published its own."""
    out = _read(where, "for-each-ref", "--format=%(objectname):%(symref) %(refname)",
                *(f"refs/heads/{name}" for name in sorted(watched)))
    return [os.fsdecode(line) for line in out.splitlines() if line]


def _state(checkout: str, repo: str, watched: set[str]) -> list[str]:
    """What the checkout holds: its HEAD, the main line, the index entries git
    has been told to skip, and the mode and content of every path the scope
    check calls changed — plus where the REPOSITORY's own main line stands.
    Read before and after each gate.

    The repository's refs are read whatever checkout the gate ran in, because
    the clone only stops the writes git makes from INSIDE it: a gate line that
    names the repository's `--git-dir` reaches straight past it, and with the
    gate box unavailable — a fallback the loop reports and runs anyway — that
    write lands on the real `main` (Codex, on the first version of this
    isolation). It cannot be prevented from here; it is refused instead.

    `changed_outside` with nothing owned is the loop's one reader of a dirty
    tree: NUL-safe, naming each file inside a new untracked directory, and
    already forgiving the caches a gate leaves behind.
    """
    # ponytail: git decides which paths are read, so a gate that edits only an
    # ignored path or a build artefact is not seen, and a gate that restores a
    # file's stat data exactly (or turns core.trustctime off) hides an edit from
    # the status read — hashing all 759 MB of tracked content would cost 2.5s
    # before and after every gate. The upgrade path is the one ecb18d23 named, a
    # read-only bind of the repository under the gate, which stops both — and
    # would also stop the third, a gate writing to the repository's refs by
    # path, which the line below can only catch after the fact.
    from worktree import changed_outside
    head = os.fsdecode(_read(checkout, "rev-parse", "HEAD")).strip()
    return ([f"{head} HEAD"] + _main_line(checkout, watched) + _flags(checkout)
            + [f"{line} (the repository's own)" for line in _main_line(repo, watched)]
            + [f"{_fingerprint(pathlib.Path(checkout, path))} {path}"
               for path in changed_outside(checkout, [])])


def combined_tree_red(repo: str, task_id: str, commit: str, gates: list, workspace=None):
    """The first failing gate on the tree this commit would publish, as
    a GateFailure with its full result — None when every gate passes.

    The builder's own kind of checkout at the candidate commit, thrown away
    afterwards: two lanes that each pass alone can still be red together, and
    the branch is what a person reads. A `Worktree` — a private clone with its
    own `.git`, the ref hook and the runtime material — because a LINKED
    worktree shares the repository's refs, and a gate that moved
    `refs/heads/main` moved the real main line before anything noticed (astra
    round 3, finding 1). What git does to a ref from inside the checkout now
    lands in the clone and is thrown away with it; a gate line that names the
    repository's own `--git-dir` still reaches it, so the repository's protected
    refs are part of the fingerprint below and any change refuses the keep.

    Raises when there is no proof to be had: the tree could not be checked out,
    or a gate edited it and so judged something the branch will never hold.
    """
    from gates import run_gate
    from keep_branch import protected
    from worktree import Worktree
    watched = protected(repo)   # the REPOSITORY's main lines: a clone has no remote to name them
    tree = Worktree(repo, f"keep-check-{task_id}", commit)
    try:
        try:
            checkout = tree.create().path
        except RuntimeError as why:
            # No tree, no proof: a checkout that could not be made is not a pass.
            raise RuntimeError(f"{task_id}: could not check out the candidate tree: "
                               f"{str(why)[:200]}") from why
        before = _state(checkout, repo, watched)
        # One shell each: joining raw gate strings with && let a `;` in one of
        # them swallow an earlier gate's failure.
        for one in gates:
            result = run_gate(one, checkout,
                              **(gate_paths.options(workspace) if workspace else {}))
            changed = set(_state(checkout, repo, watched)) ^ set(before)
            if changed:
                # A gate that edits the tree it judges judges its own work: the
                # later gates read the edit, and the branch is published without
                # it. Asked before the verdict, because a gate that mutates AND
                # fails is a defective gate too, and sending its card back for a
                # rebuild would burn rounds on text no builder can fix.
                raise GateMutatedTree(
                    f"{task_id}: a gate changed the candidate tree or the repository's own "
                    f"refs, so the gates did not judge the commit — the gate: {one[:160]} "
                    f"— what changed: "
                    + ", ".join(sorted({entry.split(" ", 1)[-1] for entry in changed})[:5]),
                    gate=one)
            if not result.passed:
                return GateFailure(one, result, commit, checkout)
        return None
    finally:
        tree.remove()
