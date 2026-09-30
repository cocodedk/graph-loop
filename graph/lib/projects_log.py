"""Recording the folder of a lean run in `graph-loop/projects` of the state folder (read by loops_projects)."""

from __future__ import annotations

import fcntl   # ponytail: POSIX only like the /proc reading of loops_ps, a lock file on Windows
import os

from loops_projects import path


def record(repo: str) -> None:
    """Add `repo`'s resolved folder as a line unless it is there; a file that cannot be written is let be.
    The check and the append happen under one lock, so two starts at once add it once."""
    folder, file = os.path.realpath(repo), path()
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("a+", encoding="utf-8") as out:
            fcntl.flock(out, fcntl.LOCK_EX)      # released when the file closes
            out.seek(0)
            text = out.read()
            if folder not in text.split("\n"):
                out.write(("\n" if text and not text.endswith("\n") else "") + folder + "\n")
    except (OSError, ValueError):
        pass
