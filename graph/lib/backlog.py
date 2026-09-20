"""The backlog is the only task source: read it, pick what can run, write it back.

The backlog file's own header states the
contract every task carries — `id`, `goal`, `status`, `needs`, `files`, `gate`,
`done_when` — and this module never invents a field or a task. A planner may slice
a task into smaller ones; `slice_task` writes the pieces back with the parent's id
in their `needs`, so the order the backlog declares survives the slicing.
"""

from __future__ import annotations

import contextlib
import fcntl
import pathlib
import threading

import backlog_tree
import durable
import frontier
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog_slice import slice_rows
from backlog_status import (  # the vocabulary, and this file's front door for it
    CODE,
    EVIDENCE,
    settled,
)


class Backlog:
    """One backlog, read on every call so a hand edit is never lost.

    Either shape: one file of tasks, or a tree of molecules with one file per
    atom (`backlog_tree`). Only `_read` and `_write` know which.
    """

    def __init__(self, path: str | pathlib.Path):
        if not str(path):   # "" is pathlib's CURRENT DIRECTORY: campaign_of.backlog_of says why
            raise ValueError("no backlog path: a campaign with no init event has none")
        self.path = pathlib.Path(path)
        self._depth = threading.local()

    @property
    def is_tree(self) -> bool:
        return self.path.is_dir()

    def read(self) -> dict:
        """The backlog as it stands, and never a wait: `_write` renames a
        finished file into place, so a reader cannot see half of one. Taking
        the writer's lock here made the board wait behind a keep."""
        return self._read()

    def _read(self) -> dict:
        if self.is_tree:
            return backlog_tree.read(self.path)
        return yaml.safe_load(self.path.read_text("utf-8"))

    def tasks(self) -> list[dict]:
        return list(self.read().get("tasks") or [])

    def task(self, task_id: str) -> dict | None:
        for row in self.tasks():
            if row.get("id") == task_id:
                return row
        return None

    def kind(self, task: dict) -> str:
        return CODE if (task.get("files") or []) else EVIDENCE

    def ready(self) -> list[dict]:
        """Every task whose status is todo and whose needs are all done, as
        `frontier.ready` reads it — the one home for that question, shared with
        the projection into waves."""
        return frontier.ready(self.tasks())

    def startable(self, running: list[str] | None = None) -> list[dict]:
        """Ready, not held for a human, and not reaching a path another task
        holds (`frontier.startable`). One read of the file, not one per card."""
        return frontier.startable(self.tasks(), running)

    def waiting_for_human(self) -> list[dict]:
        return [row for row in self.ready() if row.get("blocked_by_human")]

    # ---------------------------------------------------------------- writing

    @contextlib.contextmanager
    def only_writer(self):
        """One writer at a time: lanes run side by side and a read-modify-write
        each would lose whichever finished first.

        Reentrant within a thread: the publish path holds it while its own gate
        list and status write read through it, and a second acquire would
        otherwise wait for a lock this very thread already has.
        """
        held = getattr(self._depth, "value", 0)
        if held:
            self._depth.value = held + 1
            try:
                yield
            finally:
                self._depth.value -= 1
            return
        # ponytail: one lock for the whole tree, per-molecule if contention shows.
        # `slice_task` spans files, and per-file locks cannot make that one write.
        lock = self.path / ".lock" if self.is_tree else self.path.with_suffix(".lock")
        with open(lock, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self._depth.value = 1
            try:
                yield
            finally:
                self._depth.value = 0
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _write(self, document: dict) -> None:
        if self.is_tree:
            backlog_tree.write(self.path, document)
            return
        # Beside and renamed: a reader never sees half a file, and needs no lock.
        durable.replace(self.path, yaml.safe_dump(document, sort_keys=False, width=100,
                                                  allow_unicode=True))

    def _apply(self, document: dict, task_id: str, fields: dict, status: str | None = None) -> dict:
        """None pops a key, anything else sets it; status is left alone when omitted."""
        for row in document.get("tasks") or []:
            if row.get("id") == task_id:
                if status is not None:
                    row["status"] = status
                fields = {**fields, "triage": None, "lost_edits": None, "keep_revision": None} if status == "done" else fields  # done ends all three; every round before keeps them
                fields = {"blocked_by_human": None, **fields} if status == "todo" else fields  # requeue clears it; loop_steps explicit True wins
                for key, value in fields.items():
                    row.pop(key, None) if value is None else row.update({key: value})
                return row
        raise KeyError(f"no task {task_id} in {self.path}")

    def set_status(self, task_id: str, status: str, **fields) -> dict:
        with self.only_writer():
            document = self._read()
            row = self._apply(document, task_id, fields, status)
            self._write(document)
            return row

    def note(self, task_id: str, **fields) -> dict:
        """Write fields without touching status: restating it from the
        picked-time task dict would revert whatever status the loop set since."""
        with self.only_writer():
            document = self._read()
            row = self._apply(document, task_id, fields)
            self._write(document)
            return row

    def slice_task(self, task_id: str, pieces: list[dict]) -> list[str]:
        """Replace one task with smaller ones that carry its dependencies.

        The parent keeps its id and becomes the piece everything downstream still
        waits for: its `needs` grow to include every piece, so nothing that
        depended on the parent can start early.
        """
        if not pieces:
            raise ValueError("a slice with no pieces would delete the task")
        with self.only_writer():     # read and write as one, or two slicers lose a piece
            document = self._read()
            ids = slice_rows(document, task_id, pieces, str(self.path))
            self._write(document)
            return ids

    def unfinished(self) -> list[dict]:
        """Everything still owed. A card that has settled — done, sliced into
        pieces that are done, or dropped — is not owed, and a dropped one used to
        be listed for ever."""
        rows = self.tasks()
        finished = settled(rows)
        return [row for row in rows if row.get("id") not in finished]
