"""The one repair the event log allows: a line a crash cut in half.

The disk filled on 2026-09-03 mid-append and left half an event behind; every
reader parses every line, so the campaign's whole memory raised until a person
removed the line by hand (an independent review). Nothing is deleted here either: the
partial bytes move into a `log_truncated` event, the shape that recovery wrote,
and the log parses again. Only the LAST line may be repaired — a broken line
with a newline after it is corruption the loop must not paper over.
"""

from __future__ import annotations

import json
import os
import pathlib

from workspace_claims import _now


def repair_tail(path: pathlib.Path) -> None:
    """Close an unfinished last line. The caller holds the campaign lock.

    Raw file IO on purpose: writing this through `Workspace.event` would take
    the lock a second time and deadlock on its own flock. The repaired log is
    built whole, written to a sibling, flushed to the platter and put in place
    with one rename: the disk that cut the line is usually still full, so the
    repair itself can die halfway, and it must then leave the partial bytes
    exactly where they are for the next attempt to keep.
    """
    if not path.exists() or not path.stat().st_size:
        return
    with path.open("rb") as handle:
        handle.seek(-1, 2)
        if handle.read(1) == b"\n":
            return                       # the common case: nothing was cut
        handle.seek(0)
        data = handle.read()
    kept = data.rfind(b"\n") + 1         # 0 when the whole file is one partial line
    partial = data[kept:]
    try:
        json.loads(partial)              # a whole event that lost only its newline
        repaired = data + b"\n"
    except ValueError:
        repaired = data[:kept] + json.dumps(
            {"at": _now(), "kind": "log_truncated", "bytes": len(partial),
             "text": partial.decode("utf-8", "backslashreplace"),
             "why": "a crash cut this line mid-write; its bytes are kept here"},
            sort_keys=True).encode("utf-8") + b"\n"
    temp = path.with_suffix(".repair")
    with temp.open("wb") as handle:
        handle.write(repaired)
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(path)                   # one rename: the log is whole, or untouched
