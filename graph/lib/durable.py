"""A record the next step depends on, put on the platter before that step runs.

A write that only reached the page cache is not on disk. Power loss between a
recovery record and the destructive step it exists for keeps the destruction
and loses the record: the salvage diff and the card that points at it before
the tree is removed, the pending-keep note before `update-ref`, the card that
says a live call is open before the call. Each of those writes goes through
here, so the step after it cannot outrun it.

The ordinary event stream does NOT: fsync on every append costs every append
and does not answer what broke there — a reader that raised on one cut line
(`workspace_log.py`).
"""

from __future__ import annotations

import os
import pathlib


def replace(path: pathlib.Path, data: str | bytes, guard=None) -> pathlib.Path | None:
    """Write `data` to `path`, and return only once the file and every
    directory entry that has to name it are on the platter.

    Written beside and renamed, so a reader never sees half of it and a death
    mid-write leaves the previous content whole. The sibling's leading dot is
    what keeps it out of every reader's glob (`molecule.ordered`, the artifact
    numbering, `keep_pending.pending`).

    `guard` is asked once, with the temporary file already on the platter and
    immediately before the rename: a false answer discards the write and
    returns None. It is how a caller says "only if nothing has changed under me
    since I looked" — a decision taken on bytes read a moment earlier is stale
    by the time the rename runs, and somebody saving inside that moment had
    their edit renamed over (an independent review).
    """
    raw = data.encode("utf-8") if isinstance(data, str) else data
    _folders(path.parent)
    beside = path.parent / f".{path.name}.tmp"
    with open(beside, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if guard is not None and not guard():
        beside.unlink(missing_ok=True)
        return None
    os.replace(beside, path)
    _sync(path.parent)        # the rename itself: without this the new name can be lost
    return path


def append(path: pathlib.Path, data: str) -> pathlib.Path:
    """Add `data` to the end of `path`, and return only once it is on the
    platter. For the one line a paid step must not outrun — the marker that
    says this task has had its call."""
    _folders(path.parent)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _sync(path.parent)        # the file may be new: its name can be lost too
    return path


def _folders(folder: pathlib.Path) -> None:
    """Make `folder`, and put the entry that names each directory this call
    creates on the platter — a folder whose own name never landed takes the
    file inside it with it. A folder an earlier step made is that step's to
    answer for; the campaign root is made once, before any run.
    """
    missing = []
    walk = folder
    while not walk.exists():
        missing.append(walk)
        walk = walk.parent
    folder.mkdir(parents=True, exist_ok=True)
    for made in reversed(missing):     # outermost first: each is named by its parent
        _sync(made.parent)


def _sync(folder: pathlib.Path) -> None:
    handle = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)
