"""The campaign's memory: rotating event log, attempts, claims and the stop flag.

Everything the loop needs to survive a crash lives in files. An event is appended
and never rewritten; the log rotates into small numbered parts so it stays
readable, and nothing is ever deleted. Only an answered call counts as an attempt
— a usage limit or a denied tool call is recorded and costs the task nothing. A
running task holds a claim with its process group, so a hard stop can find every
process it started while its worktree survives for inspection.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import pathlib
import time

EVENTS = "events.jsonl"           # the part being written; older parts are numbered
MAX_EVENTS_PER_FILE = 500         # small files are readable; huge ones are not

import durable
import watchdog_spin
from workspace_alerts import AlertsMixin
from workspace_claims import ClaimsMixin, _now
from workspace_flags import (  # noqa: F401 — STOP is this module's name too
    RESTART,
    STOP,
    FlagsMixin,
)
from workspace_lock import LockMixin
from workspace_log import repair_tail
from workspace_repo import initial_root


class Workspace(ClaimsMixin, FlagsMixin, AlertsMixin, LockMixin):
    """One campaign directory. Opening an existing one reads what it holds."""

    def __init__(self, root: str | pathlib.Path):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.turn_id = ""
        self.max_events_per_file = MAX_EVENTS_PER_FILE
        # ponytail: per-instance cache; a caller that opens a fresh Workspace
        # per call (view.py, view_sections.py) never hits it. Key on root at
        # module level if that shows.
        self._events_key: tuple | None = None    # (path, size, mtime_ns) per part
        self._events_rows: list[dict] = []

    def init(self, *, goal: str, backlog: str, branch: str = "", repo: str = "") -> Workspace:
        """Record what this campaign is pointed at, once.

        The guard asks whether an init event is HERE, not whether the events
        file exists. Any other command writing first — `approve`, in the case
        that found this — created that file, and `init` then wrote nothing
        while still printing the backlog it had been handed. Nothing in the
        campaign knew where its backlog was, and a whole plan phase landed in
        the driver's own directory (2026-09-18).
        """
        if not any(row.get("kind") == "init" for row in self.events()):
            self.event("init", goal=goal, backlog=backlog, branch=branch,
                       repo=repo or str(initial_root()))
        return self

    # ----------------------------------------------------------------- events

    def _rotate_if_full(self) -> None:
        """Keep every part small enough to read. Nothing is ever deleted."""
        path = self.root / EVENTS
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as handle:
            lines = sum(1 for _ in handle)
        if lines < self.max_events_per_file:
            return
        number = len(list(self.root.glob("events-*.jsonl"))) + 1
        path.rename(self.root / f"events-{number:04d}.jsonl")

    @contextlib.contextmanager
    def only_writer(self):
        """One writer at a time across lanes and processes: the event log, its
        rotation and the claims file are all read-modify-write. A line a crash
        cut in half is closed here, before any reader parses the log and before
        any writer appends onto it — this is the one door both of them pass."""
        lock = self.root / "campaign.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        with open(lock, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                repair_tail(self.root / EVENTS)
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def event(self, kind: str, *, synced: bool = False, **fields) -> dict:
        """Append one event. `synced` puts it on the platter before this
        returns, for the few records a step must not outrun — the marker that
        says a paid call has been bought (astra's round-3 finding 14). Every
        other append stays cheap: an fsync per append costs every append and
        answers nothing about a line a crash cut in half (`durable.py`)."""
        # `kind` is the event's own name; a caller that wants to say "kind" about
        # its own subject uses another word, and this guard says so out loud.
        fields.pop("kind", None)
        if self.turn_id:
            fields["turn"] = self.turn_id
        row = {"at": _now(), "kind": kind}
        row.update(fields)
        line = json.dumps(row, sort_keys=True) + "\n"
        with self.only_writer():
            self._rotate_if_full()
            path = self.root / EVENTS
            if synced:
                durable.append(path, line)
            else:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
        return row

    def event_files(self) -> list[pathlib.Path]:
        """Every part, oldest first: the numbered ones, then the open one."""
        parts = sorted(self.root.glob("events-*.jsonl"))
        if (self.root / EVENTS).exists():
            parts.append(self.root / EVENTS)
        return parts

    def events(self) -> list[dict]:
        with self.only_writer():   # rotation renames files: a reader must not see it half-done
            parts = self.event_files()
            key = tuple((path, (info := path.stat()).st_size, info.st_mtime_ns) for path in parts)
            if key == self._events_key:    # nothing wrote since the last call: the board polls this every 15s
                return self._events_rows
            rows = []
            for path in parts:
                rows += [json.loads(line) for line in path.read_text("utf-8").splitlines()
                         if line]
            self._events_key, self._events_rows = key, rows
            return rows

    @contextlib.contextmanager
    def step(self, task_id: str, name: str):
        """Time one step of one task, and keep whatever the caller wants said.

        Every step of every task is timed, because a campaign that cannot say
        which step owns the clock cannot be made faster.
        """
        # One clock for every duration: monotonic, never the wall clock, which
        # a backward adjustment can make a ten-second gate look like one of
        # (`throttle_gates` learns that as its lone time). Wall is for `at`.
        started = time.monotonic()
        extra: dict = {}
        try:
            yield lambda **fields: extra.update(fields)
        except Exception as error:          # recorded, then re-raised
            self.event("step", task=task_id, step=name,
                       seconds=round(time.monotonic() - started, 3),
                       error=f"{type(error).__name__}: {error}", **extra)
            raise
        self.event("step", task=task_id, step=name,
                   seconds=round(time.monotonic() - started, 3), **extra)

    def artifact(self, task_id: str, name: str, text: str) -> str:
        """Write one prompt, answer, diff or gate output down, and index it.

        Nothing is overwritten: a second artifact of the same name gets the next
        number, so a retry never hides what the first attempt saw. It is on the
        platter before this returns: a salvaged diff is the only copy of paid
        edits, and the tree it came from is removed right after (`durable.py`).
        """
        folder = self.root / "calls" / task_id   # made by the write, entries and all
        number = len(list(folder.glob(f"*-{name}.txt"))) + 1
        path = folder / f"{number:03d}-{name}.txt"
        durable.replace(path, text or "")
        self.event("artifact", task=task_id, name=name, path=str(path),
                   bytes=len(text or ""))
        return str(path)

    # --------------------------------------------------------------- attempts

    def attempt(self, task_id: str, *, account: str, kind: str,
                cost: float | None = None, tokens: int | None = None,
                failed_gate: bool = False, purpose: str = "", unstarted: bool = False) -> dict:
        """File one call. `kind` decides whether the task paid for it; `purpose`
        (e.g. "review") tells the call apart when the account alone cannot, and
        `unstarted` is the caller's proof that this one never reached the model
        (`Outcome.unstarted`: a refusal, zero spend, no denials). Only the site
        holding the outcome can say that, and a live card is handed back on it."""
        return self.event("attempt", task=task_id, account=account, outcome=kind,
                          counted=(kind == "ok"), cost=cost, tokens=tokens,
                          failed_gate=bool(failed_gate), purpose=purpose, unstarted=bool(unstarted))

    def attempts(self, task_id: str) -> int:
        return sum(1 for row in self.events()
                   if row.get("kind") == "attempt" and row.get("task") == task_id
                   and row.get("counted"))

    def needs_slice(self, task_id: str) -> bool:
        """Whether this task's gate keeps failing the same way — the reading
        lives beside the watchdog's, which groups an ending the same way."""
        return watchdog_spin.needs_slice(self.events(), task_id)
