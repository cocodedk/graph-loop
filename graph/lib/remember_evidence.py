"""Which numbered artifact a section points at, and which run wrote it.

Two reviews found the same shape of mistake here. Matching by distance in the
log picked another lane's file, because a campaign writes one stream and three
cards write into it at once. Matching by direction alone then gave a run
interrupted before its artifact landed the NEXT run's file, which is worse — it
reads as evidence. So a pointer is bounded by the one execution it belongs to,
and a run whose artifact is not inside its own bounds names no file at all.

Two things bound an execution, and either alone would be enough on some logs.
The window needs no field: from that card's previous run of the same kind to
its next one. `turn` is the field: `Workspace.event` stamps every event written
while a turn is open with it (`workspace.py`), so a gate's step and the output
it wrote carry the same one, and a log with no turns carries None throughout.
"""

from __future__ import annotations

import pathlib


def artifacts(rows: list) -> dict:
    """Where each (task, artifact name) was written, in one pass over the log."""
    found: dict = {}
    for index, row in enumerate(rows):
        try:
            if (isinstance(row, dict) and row.get("kind") == "artifact"
                    and isinstance(row.get("path"), str)):
                found.setdefault((row["task"], row["name"]), []).append(
                    (index, row["path"], row.get("turn")))
        except Exception:  # noqa: BLE001, S112 — an index entry is never worth the export
            continue
    return found


def runs(rows: list, wanted) -> dict:
    """Where each card's runs of each kind sit: the boundary between one
    execution of a card and the next one of the same kind."""
    found: dict = {}
    for index, row in enumerate(rows):
        try:
            if (isinstance(row, dict) and isinstance(row.get("kind"), str)
                    and isinstance(row.get("task"), str) and wanted(row)[0]):
                found.setdefault((row["task"], _execution(row, wanted)), []).append(index)
        except Exception:  # noqa: BLE001, S112 — an index entry is never worth the export
            continue
    return found


def _execution(row: dict, wanted) -> tuple:
    """What tells one run of a card apart from the next: its kind, and which
    step it was when the kind has several."""
    return row["kind"], str(row.get("step") or "")


def span(ran: dict, length: int, index: int, row, wanted) -> tuple:
    """The stretch of the log ONE execution of a card owns, and the turn it ran
    in: from that card's previous run of the same kind to its next one.

    Two things bound it, and either alone would be enough on some logs. The
    window needs no field and works on any log. `turn` is the field: every
    event written while a turn is open carries it (`workspace.py`, `event`),
    so a gate's step and the output it wrote carry the same one — and a log
    with no turns carries None throughout, where the window does the work.
    """
    if not (isinstance(row, dict) and isinstance(row.get("task"), str)):
        return -1, index, length, None
    where = ran.get((row["task"], _execution(row, wanted))) or [index]   # may raise; `dated` holds the guard
    at = where.index(index) if index in where else 0
    return (where[at - 1] if at else -1, index,
            where[at + 1] if at + 1 < len(where) else length, row.get("turn"))


def written_for(found: dict, task: str, name: str, after: bool, span: tuple) -> str:
    """The file name of the artifact THIS execution wrote: of this task, of
    this name, inside this execution's own span, and on the side the loop
    writes it — after the event for a gate's output, before it for an answer.

    Never the closest one, and never a neighbour's. A campaign writes one
    stream and three cards write into it at once, so distance there is a fact
    about the other lanes: it made a green gate name the red run's output. And
    a run interrupted before its artifact landed was then given the NEXT run's
    file, which is worse — it reads as evidence (two independent reviews).

    So a run whose artifact is not in its own span names no file, and the
    section says the evidence never reached the log.

    The NAME only, never the recorded path: that path is absolute, it names the
    machine the campaign ran on, and these notes are committed to the campaign
    branch where a person reads them in Obsidian.
    """
    low, index, high, turn = span
    side = [path for at, path, ran in found.get((task, name)) or []
            if low < at < high and at != index and (at > index) == after and ran == turn]
    if not side:
        return ""
    return pathlib.PurePosixPath(side[0] if after else side[-1]).name
