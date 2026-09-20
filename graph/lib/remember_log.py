"""Reading a campaign's log so that nothing in it can stop the export.

`Workspace.events` parses every line of every part and raises on the first one
a crash mangled — which is right for the loop, whose memory that log is, and
wrong for a command that only describes it. A `null` line, half an object, an
init naming no backlog, a lone surrogate that will not encode again: each took
the whole command down with a traceback, on a log the campaign itself survived.

So every line of every part, rotated ones included, is read inside its own
guard, and a line that is not a usable JSON object is counted and stepped over.
Nothing here writes: no lock is taken and no truncated line is repaired, which
is the loop's own business and not this command's.
"""

from __future__ import annotations

import json


def rows(space) -> tuple[list[dict], int]:
    """Every event the log holds, in order, and how many lines could not be
    read as one."""
    kept: list[dict] = []
    lost = 0
    for path in _parts(space):
        try:
            text = path.read_text("utf-8", errors="replace")
        except OSError:
            lost += 1
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            row = _row(line)
            if row is None:
                lost += 1
            else:
                kept.append(row)
    return kept, lost


def backlog(kept: list[dict]) -> str:
    """The backlog the first init event that actually names one points at.

    Never the first init event: a campaign whose `approve` ran before its
    `init` recorded one that names nothing, and an init a crash cut in half
    names nothing either. Both are stepped over for one that does.
    """
    for row in kept:
        named = row.get("backlog")
        if row.get("kind") == "init" and isinstance(named, str) and named.strip():
            return named
    return ""


def _parts(space) -> list:
    """Every part of the log, oldest first. Asked of the workspace, which is
    the one place that knows how the parts are named and numbered."""
    try:
        return list(space.event_files())
    except OSError:
        return []


def _row(line: str) -> dict | None:
    """One line as the event it holds, or None when it is not one.

    It must also survive being written out again: an event carrying a lone
    surrogate parses happily and then raises at the moment a note is encoded,
    which is far away from the line that caused it.
    """
    try:
        row = json.loads(line)
        if not isinstance(row, dict):
            return None
        json.dumps(row, ensure_ascii=False).encode("utf-8")
    except Exception:  # noqa: BLE001 — one line is never worth the rest of the log
        return None
    return row
