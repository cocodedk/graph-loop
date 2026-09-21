"""Keeping what the loop accepts: one commit per task, on a campaign branch.

The first driver left accepted work in a temporary worktree. Two things went
wrong with that, both quietly: a reboot or a `/tmp` sweep would have erased a
weekend's output, and the next task — cut from the unchanged `HEAD` — would have
built as if its dependency had never been done.

So an accepted task is committed here, on a branch of its own, and the next task
starts from that branch's tip. The main line is never moved and never merged
into; a person does that after reading what the weekend produced.
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import subprocess

import keep_pending
from keep_branch import checked_destination, plain, resolve
from keep_gate import (  # CombinedGateFailed is raised here and named by `from keep import`
    CombinedGateFailed,
    combined_tree_red,
)
from keep_remote import push as push_branch

# the git runner, the staged names and the merge onto the tip live next door
from keep_tree import git as _git
from keep_tree import merged, staged_names


class Keeper:
    """One campaign branch, and the commits the loop puts on it."""

    def __init__(self, repo: str, branch: str, base: str = "HEAD"):
        self.repo = str(repo)
        self.branch = checked_destination(self.repo, branch)
        self.base = base

    def exists(self) -> bool:
        return bool(resolve(self.repo, self.branch))

    def tip(self) -> str:
        """Where the next task starts: the campaign's own tip, or the base."""
        return resolve(self.repo, self.branch) or _git(self.repo, "rev-parse",
                                                       self.base).strip()

    def keep(self, task_id: str, worktree: str, message: str,
             files: list[str] | None = None, attempt: int = 1, gates=None,
             record=None, publishing=None) -> str | None:
        """Commit a task's work onto the campaign branch. Returns the commit id.

        Nothing to commit answers None: an accepted task that changed no file is
        a fact worth recording, not an empty commit.
        """
        # `add --` on a path git no longer has (a rename's source) fails the whole
        # commit, so removals are staged with `-A` on the same paths.
        add = ["add", "-A", "--"] + list(files) if files else ["add", "-A"]
        _git(worktree, *add)
        staged = staged_names(worktree)
        if not staged:
            return None
        # Callers pass a free-text goal, never a Conventional Commits type, so
        # `chore` is the generic type; the card id stays in the scope, where
        # the repository's own commit hook and this test both expect it.
        subject = f"chore({task_id}): {message}".strip()[:100]
        # The commit is built on the branch's CURRENT tip, never on the
        # worktree's base: a task keeps building while others are kept, and a
        # commit parented on its stale base would silently discard every keep
        # since — that is how T1's commit fell off the branch. The task's own
        # files are overlaid, in a private index, on the tree the worktree was
        # CUT from, and that candidate is then merged onto the tip: a file
        # another card kept meanwhile keeps its change, and a real clash
        # refuses the keep instead of overwriting it. The ref moves only if
        # the tip has not moved again meanwhile.
        tip = self.tip()
        base = _git(worktree, "rev-parse", "HEAD").strip()
        index = pathlib.Path(self.repo) / ".git" / f"keep-index-{task_id}"
        env = {"GIT_INDEX_FILE": str(index)}
        try:
            _git(self.repo, "read-tree", base, env=env)
            for name in staged:
                source = pathlib.Path(worktree) / name
                # `.exists()` follows a symlink: a live one would read as its
                # target's content and mode, a dangling one as absent. Checked
                # first and by `.is_symlink()`, which looks at the link itself.
                # Written into the REPO's object store: a task checkout is a
                # private clone that reads the repo's objects via alternates but
                # cannot write there, so `-w` runs `-C self.repo` — a file by its
                # absolute path, since git reads any path, tracked or not.
                if source.is_symlink():
                    blob = _git(self.repo, "hash-object", "-w", "--stdin",
                               stdin=os.readlink(os.fsencode(source))).strip()
                    _git(self.repo, "update-index", "--add",
                         "--cacheinfo", f"120000,{blob},{name}", env=env)
                elif source.exists():
                    blob = _git(self.repo, "hash-object", "-w", "--", str(source)).strip()
                    mode = "100755" if source.stat().st_mode & 0o100 else "100644"
                    _git(self.repo, "update-index", "--add",
                         "--cacheinfo", f"{mode},{blob},{name}", env=env)
                else:
                    _git(self.repo, "update-index", "--force-remove",
                         "--", name, env=env)
            tree = _git(self.repo, "write-tree", env=env).strip()
            candidate = _git(self.repo, "commit-tree", tree, "-p", base,
                             "-m", subject, env=env).strip()
        finally:
            index.unlink(missing_ok=True)
        commit = _git(self.repo, "commit-tree", merged(self.repo, task_id, tip, candidate),
                      "-p", tip, "-m", subject).strip()
        name = f"refs/heads/{plain(self.branch)}"
        # The old-value guard: an existing branch must still be at the tip the
        # commit was built on; a first keep must still be creating the ref.
        # `gates` is a callable: the list is asked for again on every attempt, so a
        # sibling that landed since the last try is gated too.
        with (publishing() if publishing else contextlib.nullcontext()):
            return self._publish(task_id, worktree, message, files, attempt, gates, record,
                                 publishing, commit, tip, name)

    def _publish(self, task_id, worktree, message, files, attempt, gates, record,
                 publishing, commit, tip, name):
        if self.tip() != tip:
            # A sibling published while this commit was being built: gating a stale
            # candidate would fail for the wrong reason, so it is rebuilt first.
            if attempt >= 3:
                raise RuntimeError(f"the branch moved under {task_id} three times")
            return self.keep(task_id, worktree, message, files, attempt=attempt + 1,
                             gates=gates, record=record, publishing=publishing)
        wanted = list(gates() if callable(gates) else (gates or []))
        red = self._combined_tree_red(task_id, commit, wanted) if wanted else None
        if red:
            # This card passed alone, but a sibling landed meanwhile: the two
            # together are what the branch will hold, so the gate runs on THAT
            # tree before the ref moves. A red combination is not published —
            # and the refusal carries the failing gate's own words: a mute
            # combined failure consumed T4.close's last two rounds telling nobody why.
            gate, tail = red.gate, red.result.output[-400:].strip()
            raise CombinedGateFailed(
                f"{task_id}: the gate fails on the branch with the work that landed first — "
                f"the failing gate: {gate[:160]} — its last words: {tail or '(it printed nothing)'}",
                gate=gate, base=tip, failure=red)
        # Construction's answer goes stale — a worktree can check the branch out
        # meanwhile — so it is asked again, before the note names a commit.
        checked_destination(self.repo, self.branch)
        # Written and fsynced before the ref moves, so a crash between the move
        # and `record` below still leaves proof the branch holds this commit —
        # `pending()` reads it back at the next start. Atomic: a crash mid-write
        # must never leave a half-written sha for that reader to trip over.
        pending = keep_pending.note(self.repo, self.branch, task_id, commit)
        guard = tip if self.exists() else "0" * 40
        moved = subprocess.run(("git", "-C", self.repo, "update-ref", name, commit, guard),
                               capture_output=True, text=True, check=False)
        if not moved.returncode:
            if record:
                # Recorded AFTER the ref moves, so a crash never leaves the backlog
                # claiming work the branch does not hold. The gate-publish-record
                # stretch is under one lock, which serializes the WRITERS: no second
                # lane publishes inside it. A reader takes no lock and sees the last
                # whole document, which is why `Backlog._write` renames into place.
                record(commit)
            pending.unlink(missing_ok=True)
        if moved.returncode:
            # Another lane published between the read and the write: the guard did
            # its job, and this keep is built again on the new tip rather than lost.
            if attempt >= 3:
                raise RuntimeError(f"the branch moved under {task_id} three times: {moved.stderr.strip()[:200]}")
            return self.keep(task_id, worktree, message, files, attempt=attempt + 1, gates=gates,
                             record=record, publishing=publishing)
        return commit

    def _combined_tree_red(self, task_id: str, commit: str, gates: list):
        """The first failing gate on the tree this commit would publish, as
        a GateFailure with its full result — None when every gate passes. Body lives in `keep_gate.py`."""
        return combined_tree_red(self.repo, task_id, commit, gates)

    def push(self, remote: str = "origin") -> str:
        """Push the campaign branch. Body lives in `keep_remote.py`."""
        return push_branch(self.repo, self.branch, remote)

    def pending(self) -> list[tuple[str, str]]:
        """A crash left standing: the ref moved, but the card-write that marks
        it done never ran. Body lives in `keep_pending.py`."""
        return keep_pending.pending(self.repo, self.branch)

    def settle(self, task_id: str) -> None:
        """`task_id`'s card is written: its recovery note is no longer needed."""
        keep_pending.settle(self.repo, self.branch, task_id)
