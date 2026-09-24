"""Read every closed ending that TRIAGE has not processed.

The full ordered campaign log is the cursor. A release closes a lane ending;
if release itself fails, the task's next claim closes the old ending. A
quarantine made outside a lane is its own ending. Open endings wait.
"""

from __future__ import annotations

import dataclasses
import pathlib

MAX_ARTIFACT_BYTES = 100_000
OUTCOMES = {
    "accepted", "failed", "needs_a_person", "quarantined", "rebuild_queued",
    "refused", "rejected", "review_unavailable",
}


@dataclasses.dataclass(frozen=True)
class Ending:
    task: str
    card: dict
    events: tuple[dict, ...]
    artifacts: dict[str, tuple[str, ...]]
    gate_outputs: tuple[str, ...]
    closed_at: str = ""
    closed_index: int = -1
    closed_kind: str = ""


def pending_endings(book, space) -> list[Ending]:
    """Closed endings after each task's last verified full-log cursor."""
    rows = space.events()
    cards = {str(row.get("id")): row for row in book.tasks()}
    cursors = _cursors(rows)
    cache: dict[int, str | None] = {}

    def read_artifact(index: int, event: dict) -> str | None:
        if index not in cache:
            cache[index] = _read(event.get("path"), space.root)
        return cache[index]

    out = []
    for task, start, body_stop, close in _closures(rows):
        if not _after_cursor(rows, close, cursors.get(task)):
            continue
        closing = rows[close]
        own = _own(rows, task, start, body_stop, close)
        artifacts: dict[str, list[str]] = {}
        for index in range(start, body_stop):
            event = rows[index]
            if event.get("task") != task:
                continue
            if event.get("kind") != "artifact":
                continue
            text = read_artifact(index, event)
            if text is not None:
                artifacts.setdefault(str(event.get("name") or ""), []).append(text)
        history = tuple(
            text for index, event in enumerate(rows[:close + 1])
            if event.get("kind") == "artifact" and event.get("task") == task
            and event.get("name") == "gate-output"
            if (text := read_artifact(index, event)) is not None)
        out.append(Ending(task, cards.get(task, {"id": task}), own,
                          {name: tuple(texts) for name, texts in artifacts.items()},
                          history, str(closing.get("at") or ""), close,
                          str(closing.get("kind") or "")))
    return out


def words(ending: Ending) -> str:
    """The bounded human-readable evidence used by signatures and the model."""
    said = ""
    pieces = [str(row.get("why") or "") for row in ending.events if row.get("why")]
    for texts in ending.artifacts.values():
        pieces.extend(texts)
    for piece in pieces:
        said = (said + "\n" + piece)[-20_000:]
    return said


def has_outcome(ending: Ending) -> bool:
    return any(event.get("kind") in OUTCOMES for event in ending.events)


def _own(rows: list[dict], task: str, start: int, stop: int,
         close: int) -> tuple[dict, ...]:
    closing_quarantine = rows[close].get("kind") == "quarantined"
    return tuple(event for event in rows[start:stop]
                 if event.get("task") == task
                 and (closing_quarantine or event.get("kind") != "quarantined"))


def _closures(rows: list[dict]) -> list[tuple[str, int, int, int]]:
    """(task, body start, body stop, full-log closing index), in log order."""
    starts: dict[str, int] = {}
    out = []
    for index, row in enumerate(rows):
        task = str(row.get("task") or "")
        if not task:
            continue
        if row.get("kind") == "claimed":
            if task in starts:
                out.append((task, starts[task], index, index))
            starts[task] = index
        elif row.get("kind") == "released" and task in starts:
            out.append((task, starts.pop(task), index + 1, index))
        elif row.get("kind") == "quarantined":
            out.append((task, index, index + 1, index))
    return out


def _cursors(rows: list[dict]) -> dict[str, dict]:
    return {str(row.get("task")): row for row in rows
            if row.get("kind") == "triage" and row.get("task")}


def _after_cursor(rows: list[dict], close: int, cursor: dict | None) -> bool:
    if cursor is None:
        return True
    try:
        index = int(cursor["closed_index"])
        closing = rows[index]
        valid = (closing.get("task") == cursor.get("task")
                 and closing.get("at") == cursor.get("closed_at")
                 and closing.get("kind") == cursor.get("closed_kind"))
    except (IndexError, KeyError, TypeError, ValueError):
        valid = False
        index = -1
    if valid:
        return close > index
    # A stale full-log index replays rather than loses: time is provenance only
    # on the healthy path, and the conservative fallback includes equal seconds.
    return str(rows[close].get("at") or "") >= str(cursor.get("closed_at") or "")


def _read(raw, root: pathlib.Path, *, tail: bool = True) -> str | None:
    if not raw:
        return None
    try:
        path = pathlib.Path(str(raw)).resolve()
        path.relative_to(pathlib.Path(root).resolve())
        with path.open("rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - MAX_ARTIFACT_BYTES) if tail else 0)
            return handle.read(MAX_ARTIFACT_BYTES).decode("utf-8", "replace")
    except (OSError, RuntimeError, ValueError):
        return None
