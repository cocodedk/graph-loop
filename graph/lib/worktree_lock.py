"""One holder at a time on the shared live stack. Split from `worktree` at
the 200-line cap; `worktree` stays the front door (`from worktree import
LiveLock`)."""

from __future__ import annotations

import contextlib
import fcntl
import os
import pathlib
import pwd
from collections.abc import Iterator

import workspace_claims

LOCK = "live-stack.lock"
GUARD = LOCK + ".guard"
LOCK_WAITS = 2
"""How many turns a card waits on a lock nobody can read before the loop
owns it. Two, not one: a record written this second is unreadable for a
moment, and still unreadable a turn later is a fault, not a moment."""
LIVE_STACK = "graph-live"
"""The one stack this loop drives: the compose project name every
`docker compose -p` in the helper at `tools.helper()`
(`GRAPH_HELPER`) passes."""


def shared() -> str:
    """The one folder the live-stack lock lives in, for every driver on this
    host. Answers a path; the folder is made where the file is opened.

    NOTHING in the environment decides it, and nothing may be added that does:
    the uid comes from the kernel and the home from the passwd database, so a
    gate sandbox that rewrites `HOME`, a test process that sets `TMPDIR`, and a
    driver started with a different `XDG_RUNTIME_DIR` all meet the same file.
    Two names for one lock is two drivers on one stack — `TMPDIR` was that
    defect, and `GRAPH_LIVE_LOCK`, added to keep the suite off this host's own
    lock, was the same defect wearing the loop's own initials. A suite stands
    in for this function instead. And a fixed home always exists, so there is
    no second place to fall back to and no branch to get wrong. A lock left
    behind by a reboot is no hazard: the record carries this boot's id, and
    `holder_is_gone` reads a record from another boot as gone.
    """
    return str(pathlib.Path(pwd.getpwuid(os.getuid()).pw_dir)
               / ".cache" / "graph-loop" / LIVE_STACK)


def stack_lock() -> LiveLock:
    """The lock on the live stack — the one every driver on this host means.

    The one door to it, so `shared` is read here at every call and a test
    isolates itself by standing in for that one name.
    """
    return LiveLock(shared())


@contextlib.contextmanager
def _exclusive(path: pathlib.Path) -> Iterator[None]:
    """One writer at a time through reading the holder, deleting it and
    publishing a new one. Two drivers that both read one dead holder used to
    both delete it and both publish, and the second record replaced the first
    with neither driver told. The guard file is never removed — a lock taken
    on a file another writer has already unlinked guards nothing."""
    guard = path.with_name(GUARD)
    guard.parent.mkdir(parents=True, exist_ok=True)
    with open(guard, "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


class LiveLock:
    """One holder at a time on the shared stack; the file names who holds it.

    The holder is a process, named the way a claim names one: pid, this boot's
    id and the process's start tick. The group was the old shape, and the
    driver shares its group with the supervisor that restarts it — so a
    hard-killed driver's lock read as held for ever and every later live card
    waited on a process that was gone. Claims were fixed; the lock was not.
    """

    def __init__(self, folder: str):
        self.path = pathlib.Path(folder) / LOCK
        self.record: str | None = None    # what THIS object published, if it took it

    def take(self, task_id: str) -> bool:
        tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        record = f"{task_id} {os.getpid()} {workspace_claims._started(os.getpid()) or ''}"
        # Reading the holder, clearing a dead one and publishing this one are
        # one hold: apart, a driver that cleared the same dead lock a moment
        # earlier lost the record it had just written.
        with _exclusive(self.path):
            # A living holder keeps it, whatever task the record names: a second
            # driver on the same card read its own id here and freed a lock in use.
            if self.holder_is_gone():
                self.path.unlink(missing_ok=True)
            # Written whole under a throwaway name, then published in one move: a
            # reader of `self.path` never meets a holder that is half written.
            # `os.link` -- not `os.replace` -- because it fails if the lock already
            # exists: the publish is exclusive as well as atomic, so two takers
            # can never both believe they hold it.
            try:
                tmp.write_text(record, "utf-8")
                os.link(tmp, self.path)
            except FileExistsError:
                return False
            finally:
                tmp.unlink(missing_ok=True)
        self.record = record
        return True

    def holder(self) -> str | None:
        try:
            parts = self.path.read_text("utf-8").split()
            return parts[0] if parts else None
        except FileNotFoundError:
            return None

    def holder_is_gone(self) -> bool:
        """A killed driver leaves its lock behind; a dead holder holds nothing.

        A lock this cannot read is HELD, not free: a doubt never abandons
        someone else's claim, and a lock taken by a lock that cannot be read
        is two drivers on one stack. An EMPTY lock is no exception: a file
        exists, so someone was there; a person clears it, not this check.
        """
        try:
            text = self.path.read_text("utf-8").strip()
        except FileNotFoundError:
            return True
        parts = text.split()
        if len(parts) < 2:
            return False
        row = {"pid": parts[1], "started": parts[2] if len(parts) > 2 else ""}
        return not workspace_claims._alive(row)

    def unreadable(self) -> bool:
        """A lock file that exists and names no holder anyone can check.

        Held, exactly as `holder_is_gone` says — a doubt never abandons someone
        else's claim, and what cannot be read cannot be cleared. But not a
        living holder either: nothing here can be asked whether it is alive, so
        a card waiting on it waits for ever. The caller records that as an
        infrastructure failure and, after `LOCK_WAITS` turns, hands the card to
        the plan phase instead of waiting again (astra round 4, finding 10).
        """
        try:
            return len(self.path.read_text("utf-8").split()) < 2
        except FileNotFoundError:
            return False       # no lock at all: nothing to doubt
        except (OSError, ValueError):
            return True        # there, and no reader can say who holds it

    def mine(self) -> bool:
        """Whether the lock on disk is the one THIS object published. The
        record decides, not the pid: two holders inside one process — a second
        campaign, a test — would each read the other's pid as their own.
        ponytail: same-process holders of the same task id write the same three
        fields, so a second `give_back` on a released object would free the
        other's lock; a fourth, unique field when `test_worktree.py:161` stops
        requiring exactly three."""
        try:
            return self.record is not None and self.path.read_text("utf-8") == self.record
        except FileNotFoundError:
            return False

    def give_back(self) -> None:
        """The taker frees it, and so does anyone once the holder is gone —
        that second case is a dead driver's lock being cleared. Nobody else:
        an unlink by a driver that never took it puts two on one stack. Under
        the same hold as `take`, so the record read here is the one deleted."""
        with _exclusive(self.path):
            if self.mine() or self.holder_is_gone():
                self.path.unlink(missing_ok=True)
