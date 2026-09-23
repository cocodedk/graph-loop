"""Alerts: something a person has to read, and how much of it has been.

The loop also emails alerts through the campaign's proven contact channel.
`ALERTS.shown` is a candidate: what a render displayed, waiting on
`watch.sh --read` to confirm it. `ALERTS.read` is the commitment.

An alert is a message, never a handoff: nothing the loop does waits for that
commitment. When a decision is applied it RESOLVES the exact alerts about the
subject it decided (`ALERTS.resolved`, the line numbers themselves) — they are
answered, so they stop asking. That record is separate from the cursor on
purpose: advancing the cursor over them would carry away every unrelated and
fatal notice standing between (astra's section G).
"""

from __future__ import annotations

import json
import pathlib

import alert_email
from workspace_claims import _now

RESOLVED = "ALERTS.resolved"


class AlertsMixin:
    """Mixed into Workspace: everything here reads `self.root`, writes events
    through `self.event`, and serializes with `self.only_writer`."""

    root: pathlib.Path

    def event(self, kind: str, **fields) -> dict:  # provided by Workspace
        raise NotImplementedError

    def only_writer(self):                        # provided by Workspace
        raise NotImplementedError

    def require_contact(self) -> str:
        path = self.root / "contact"
        channel = path.read_text("utf-8").strip() if path.exists() else ""
        if not channel:
            raise SystemExit('no proven channel — run `graph-goal.py contact "<email-address>"` first')
        return channel

    def notify_person(self, row: dict) -> None:
        if row["kind"] not in ("needs_a_person", "slice_needs_person", "alert"):
            return
        if not (self.root / "contact").exists():
            return
        try:
            alert_email.send(row["kind"], json.dumps(row, sort_keys=True),
                             recipient=self.require_contact())
        except (OSError, ValueError, SystemExit) as error:
            self.event("contact_send_failed", about=row["kind"], error=str(error))

    def alert(self, task_id: str, what: str, *, limit: int | None = 300) -> str:
        """Log and send something a person has to read, newest last."""
        line = f"{_now()}  {task_id}  {' '.join(str(what).split())[:limit]}\n"
        with self.only_writer(), (self.root / "ALERTS.txt").open("a", encoding="utf-8") as handle:
            handle.write(line)
        # event() takes only_writer itself; flock is per open file description, not
        # re-entrant, so calling it while the block above still held the lock would
        # deadlock the process against itself. It runs after the lock is released.
        self.event("alert", task=task_id, why=str(what)[:limit])
        return line

    def alerts(self, unread_only: bool = True) -> list[str]:
        lines = self._rows()
        if not unread_only:
            return lines
        return [line for _at, line in self._open(lines, self._read(), self._resolved())]

    def alerts_snapshot(self) -> tuple[list[str], list[int]]:
        """The alerts still asking for something and THEIR OWN line numbers,
        both read under one lock — the same instant, never two. A caller that
        renders fewer than every row marks the last one it displayed, plus one:
        `positions[rendered_count - 1] + 1`.

        The numbers are handed over rather than worked out from the count,
        because a resolved alert leaves a gap: arithmetic over the count ran
        the mark past a row nobody had seen, and the next `--read` confirmed it
        (Codex, finding 8).

        Reads the files itself, inside one lock. `alerts()` stays unlocked
        and is not called here: callers of it may already hold the lock.
        """
        with self.only_writer():
            lines, read, resolved = self._rows(), self._read(), self._resolved()
        rows = self._open(lines, read, resolved)
        return [line for _at, line in rows], [at for at, _line in rows]

    def alert_ids(self, task_id: str) -> list[int]:
        """The line numbers of the alerts about `task_id` standing right now.

        Read apart from the resolving, because what a decision answers is what
        stood when it was made: an alert its own application writes — a salvage
        that could not save the paid edits — is news, and resolving by name
        after the fact hid it at once (Codex, finding 9).
        """
        with self.only_writer():
            return [index for index, line in enumerate(self._rows())
                    if _about(line, task_id)]

    def resolve_alert_ids(self, ids: list[int]) -> list[int]:
        """Answer exactly these alerts and no others: their line numbers are
        recorded, so a notice about anything else — and one written since —
        still asks.

        The read cursor is not touched. It says what a PERSON has read, and a
        decision is not a person.
        """
        with self.only_writer():
            resolved = sorted(self._resolved() | {int(one) for one in ids})
            (self.root / RESOLVED).write_text(json.dumps(resolved), "utf-8")
        return list(ids)

    def resolve_alerts(self, task_id: str) -> list[int]:
        """Answer the alerts about `task_id` that stand right now. The two
        steps above, for a caller with nothing to do between them."""
        return self.resolve_alert_ids(self.alert_ids(task_id))

    def _rows(self) -> list[str]:
        path = self.root / "ALERTS.txt"
        return [line for line in path.read_text("utf-8").splitlines() if line.strip()] \
            if path.exists() else []

    def _read(self) -> int:
        # The mark is a count, because two alerts can carry the same words and a
        # text mark would hide the second behind the first.
        try:
            return int((self.root / "ALERTS.read").read_text("utf-8").strip())
        except (FileNotFoundError, ValueError):
            return 0

    def _resolved(self) -> set[int]:
        try:
            return set(json.loads((self.root / RESOLVED).read_text("utf-8")))
        except (OSError, ValueError):
            return set()

    @staticmethod
    def _open(lines: list[str], read: int, resolved: set[int]) -> list[tuple[int, str]]:
        """The rows still asking, with their line numbers."""
        return [(index, line) for index, line in enumerate(lines)
                if index >= read and index not in resolved]

    def _mark_bounded(self, filename: str, candidate: int) -> None:
        """Write `max(existing, candidate)` to `filename`, refusing a
        candidate that names an alert never written. Caller holds
        `only_writer` — this does not lock on its own."""
        rows_path = self.root / "ALERTS.txt"
        total = 0
        if rows_path.exists():
            total = sum(1 for line in rows_path.read_text("utf-8").splitlines()
                        if line.strip())
        if not 0 <= candidate <= total:
            raise ValueError(
                f"{filename}: cannot mark {candidate}, only {total} alerts exist")
        path = self.root / filename
        try:
            current = int(path.read_text("utf-8").strip())
        except (FileNotFoundError, ValueError):
            current = 0
        path.write_text(str(max(current, candidate)), "utf-8")

    def alerts_read(self, shown: int) -> None:
        """Mark `shown` read — never backward, and never past what
        `ALERTS.txt` actually holds: a delayed older mark must never
        overwrite a newer one that already landed."""
        with self.only_writer():
            self._mark_bounded("ALERTS.read", shown)

    def alerts_shown(self, position: int) -> None:
        """Mark `position` shown — the same bounded, monotonic write as
        `alerts_read`, for what a render displayed but nobody has confirmed
        reading yet."""
        with self.only_writer():
            self._mark_bounded("ALERTS.shown", position)


def _about(line: str, task_id: str) -> bool:
    """Whether this alert line is about that subject. The line is written by
    `alert` as `<when>  <task>  <what>`, so the subject is read from where it
    was written, never matched anywhere in the words."""
    parts = line.split("  ")
    return len(parts) > 1 and parts[1].strip() == task_id
