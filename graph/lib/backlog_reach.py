"""What a card touches, and whether two cards touch the same thing.

Pure functions over a card's declared paths, kept beside the backlog because
they read a card and never the file. Two lanes may not share a path, the
directory it sits in, or a sibling slot.
"""

from __future__ import annotations

import pathlib


def reach(row: dict) -> set:
    """Every path a task can touch: its own files, anything under a directory
    it owns, and — when it may add files — the directories those files sit in.
    Two lanes that share any of it would overwrite each other's work."""
    paths = {str(p).rstrip("/") for p in (row.get("files") or [])}
    reach = set(paths)
    for path in paths:
        reach.add(path + "/")                      # a directory grant reaches beneath it
        if row.get("may_add_files"):
            parent = str(pathlib.PurePosixPath(path).parent)
            # a root file's parent is "."; as "./" it would overlap nothing,
            # so the repository root is named "" and reaches every path.
            reach.add("" if parent == "." else parent + "/")
    return reach

def overlap(one: set, two: set) -> bool:
    for a in one:
        for b in two:
            if a == b or a == "" or b == "":       # "" is the repository root
                return True
            if a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/"):
                return True
    return False
