"""Shared heartbeat freshness rule for the drive campaign's supervisor:
alert-watcher.sh's routing (via `python3 -c`) and stale_flags.py's
15-minute escalation hold must agree on what "fresh" means, or one warns
while the other holds silently for the very same board.
"""

from __future__ import annotations

import pathlib
import time

FRESH_MINUTES = 30


def is_fresh(path: pathlib.Path, minutes: int = FRESH_MINUTES) -> bool:
    """A heartbeat file that exists and was touched within `minutes`. A
    missing file is never fresh here — a caller that wants a different
    default for "no file yet" (alert-watcher.sh's routing does, to route
    to WATCHER before its first wake) decides that itself."""
    return path.is_file() and (time.time() - path.stat().st_mtime) < minutes * 60


def watching(campaign_dir: pathlib.Path | str) -> str | None:
    """The name of the actor whose heartbeat is fresh right now — WATCHER
    checked first, since it is the primary — or None if neither is."""
    d = pathlib.Path(campaign_dir)
    for name in ("WATCHER", "WATCHER-STANDIN"):
        if is_fresh(d / f"{name}.heartbeat"):
            return name
    return None
