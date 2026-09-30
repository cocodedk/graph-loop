"""Reading the folders a lean loop has run on: one absolute folder a line in `graph-loop/projects` of the state folder."""

from __future__ import annotations

import os
import pathlib


def path() -> pathlib.Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return pathlib.Path(base, "graph-loop", "projects")


def folders() -> list[str]:
    """The recorded folders in file order, each exactly as written; none when the file is missing or unreadable."""
    try:
        return [line for line in path().read_text("utf-8").split("\n") if line]
    except (OSError, ValueError):
        return []
