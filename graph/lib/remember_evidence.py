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


def runs(rows: list, wanted=None) -> dict:
    """Where each card's executions of each step sit.

    `Workspace.step` writes one event per execution of a step, and THOSE are
    what bound it — never the outcomes. A refusal bounded by the refusals
    around it reaches back over a review that PASSED, because a passing review
    writes an answer and no refusal at all, and it then named that answer as
    its own evidence (an independent review).
    """
    found: dict = {}
    for index, row in enumerate(rows):
        try:
            if (isinstance(row, dict) and row.get("kind") == "step"
                    and isinstance(row.get("task"), str)
                    and isinstance(row.get("step"), str)):
                found.setdefault((row["task"], row["step"]), []).append(index)
        except Exception:  # noqa: BLE001, S112 — an index entry is never worth the export
            continue
    return found


def span(ran: dict, length: int, index: int, row, wanted=None):
    """The stretch of the log ONE execution of a card owns, and the turn it ran
    in — or None when nothing in the log says this event had an execution.

    Two things bound it, and either alone would be enough on some logs. The
    window needs no field: from the `step` event that opened this execution to
    the one that opens the next. `turn` is the field: every event written while
    a turn is open carries it (`workspace.py`, `event`), so a gate's step and
    the output it wrote carry the same one, and a log with no turns carries
    None throughout.

    No enclosing `step` event means no positive proof that any artifact belongs
    to this event, and then there is no pointer at all.
    """
    if not (isinstance(row, dict) and isinstance(row.get("task"), str)
            and isinstance(row.get("step"), str)):
        return None
    where = ran.get((row["task"], row["step"])) or []
    opened = [at for at in where if at <= index]
    if not opened:
        return None
    later = [at for at in where if at > index]
    return opened[-1], index, later[0] if later else length, row.get("turn")


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
    if span is None:
        return ""
    low, index, high, turn = span
    side = [path for at, path, ran in found.get((task, name)) or []
            if low <= at < high and at != index and (at > index) == after and ran == turn]
    if not side:
        return ""
    return pathlib.PurePosixPath(side[0] if after else side[-1]).name
