"""A private checkout per task, the scope it may write, and the live-stack lock.

Three rules, each learned the hard way: a task starts from a named commit and
never from the dirty checkout somebody else is editing; a builder that writes
outside its declared files has its work refused rather than merged; and only one
task at a time may touch the shared live stack, because two runs collide on the
same targets, the same approval window and the one replan each run is allowed.
A fourth rule protects refs: each checkout is a private clone with its own
`.git`, so a builder's ref writes land only there, never reaching the repo.
`lib/hooks/reference-transaction` also refuses any such write it can see.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile

from worktree_lock import (  # noqa: F401 — the door stays here
    LOCK_WAITS,
    LiveLock,
    stack_lock,
)
from worktree_refs import (  # noqa: F401
    HeadMoved,
    advance,
    discard,
    provision,
    reuse_or_salvage,
    save_and_go,
)
from worktree_scope import (  # noqa: F401 — the door stays here
    added_beside,
    changed_outside,
)

KEEP_NOTE = "WHY-THIS-IS-KEPT.txt"
# What running a gate leaves behind. These are not edits, and counting them as
# work outside the task's files refused a correct change in the first pilot.
ARTEFACTS = ("__pycache__", ".pytest_cache", ".ruff_cache", "node_modules",
             ".mypy_cache", ".coverage")
HOOKS_DIR = str(pathlib.Path(__file__).resolve().parent / "hooks")   # beside this module, not the repo


def _git(root: str, *args: str) -> str:
    done = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                          check=False)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


class Worktree:
    """One task's checkout. `create` is the only thing that writes to the repo."""

    def __init__(self, repo: str, task_id: str, commit: str = "HEAD"):
        self.repo = str(repo)
        self.task_id = task_id
        self.commit = commit
        self.path = ""
        self.rebased: tuple[str, str] | None = None   # (old, new) when `reuse` moved HEAD

    def reuse(self, path: str) -> Worktree:
        """Attach to a checkout an earlier round already cut: a rebuild carries
        on in the worktree that holds its work, so nothing is re-derived. The
        note the previous round left is deleted — it belongs to that round, and
        left in place it would read as the builder's work: outside the task's
        files, inside the reviewer's diff, and committed by a no-files keep.

        The loop's own base can move on while this tree sits kept: `advance`
        (worktree_refs.py) catches it up, or raises `HeadMoved` on conflict.
        A `.git` FILE, not a directory, is a linked worktree from before this
        change: `git config` on it writes into the REPO's own shared config,
        and its refs are shared too. Never adopt one — treat it as lost, the
        same as a path a /tmp sweep already removed, and cut a fresh tree."""
        if not (pathlib.Path(path) / ".git").is_dir():
            return self.create()
        self.path = str(path)
        self._hooked()   # a tree cut before this hook existed must not go unprotected
        target = _git(self.repo, "rev-parse", self.commit).strip()
        found = _git(self.path, "rev-parse", "HEAD").strip()
        self.commit = advance(self.repo, self.path, found, target) or found
        self.rebased = (found, self.commit) if self.commit != found else None
        (pathlib.Path(self.path) / KEEP_NOTE).unlink(missing_ok=True)
        return self

    def create(self, parent: str | None = None) -> Worktree:
        base = parent or tempfile.mkdtemp(prefix="drive-")
        self.path = str(pathlib.Path(base) / f"task-{self.task_id}")
        # Detached at a named commit: whatever is uncommitted in the main
        # checkout — another agent's half-finished work — stays out of it.
        sha = _git(self.repo, "rev-parse", self.commit).strip()
        self.commit = sha   # a real sha from here on, never the literal "HEAD"
        # A clone, not a linked worktree: refs live in its OWN .git, never the
        # repo's shared one. `--shared` reads objects via the repo's alternates
        # instead of copying them; `--no-checkout` skips a branch since detach below does it.
        _git(self.repo, "clone", "--quiet", "--shared", "--no-checkout", self.repo, self.path)
        # No origin: `git push origin ...` writes the remote's refs before its
        # own local bookkeeping — and only that last, local step is what the
        # hook below can refuse. Objects still resolve through the alternates
        # `--shared` wrote; nothing here needs a remote to reach them.
        _git(self.path, "remote", "remove", "origin")
        _git(self.path, "checkout", "--quiet", "--detach", sha)
        self._hooked()
        provision(self.path, self.repo)   # gitignored material a suite needs (T15, 02:56)
        return self

    def _hooked(self) -> None:
        """Refs are the driver's from here on. Idempotent; `create` and `reuse`
        both call it — plain `core.hooksPath`, a full repo needs no `extensions.worktreeConfig`."""
        _git(self.path, "config", "core.hooksPath", HOOKS_DIR)

    def on_base(self) -> None:
        """HEAD still equals the round's own commit. `git switch` to a branch
        that already EXISTS reattaches HEAD by a symbolic-ref update no hook
        covers — this catches that; nothing here can reach the repo either way."""
        found = _git(self.path, "rev-parse", "HEAD").strip()
        if found != self.commit:
            raise HeadMoved(found)

    def remove(self) -> None:
        if not self.path:
            return
        shutil.rmtree(self.path, ignore_errors=True)
        # and the mkdtemp parent it sat in: an empty drive-* dir per removed
        # tree is how /tmp grew 123 of them in an hour
        parent = pathlib.Path(self.path).parent
        try:
            if parent.name.startswith("drive-") and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
        self.path = ""

    def keep(self, why: str) -> str:
        """Leave a failed task's tree where it is, with the reason inside it."""
        (pathlib.Path(self.path) / KEEP_NOTE).write_text(
            f"{why}\n\nTask {self.task_id}, from {self.commit}.\n"
            "Nothing here is merged. Read it, then delete the directory.\n", "utf-8")
        return self.path

    def diff(self, paths: list[str] | None = None, binary: bool = False,
             against: str = "HEAD") -> str:
        """The whole change, new files included; `binary` carries binary
        content too (a salvage must), where a reviewer's diff only names it.

        `git diff` hides untracked files, so a reviewer shown the plain diff of
        a task whose deliverable is a NEW test refused it for importing a module
        it could not see — and was right to. Intent-to-add makes new files part
        of the diff without staging their content anywhere durable.

        `against` is what the tree is compared with. HEAD by default — so
        anything already staged (a rename's deletion) is in the diff the
        reviewer reads, and the keeper, which commits the index, agrees with it.
        Salvaging a tree whose HEAD MOVED passes the round's recorded base
        instead: HEAD there is not the base, and a builder that put its edits
        inside its own commit leaves nothing at all in a diff against it.
        """
        _git(self.path, "add", "-N", "--", ".")
        args = ["diff", against] + (["--binary"] if binary else []) + (["--"] + list(paths) if paths else [])
        return _git(self.path, *args)
