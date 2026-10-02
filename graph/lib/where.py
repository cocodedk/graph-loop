"""Where this loop is pointed: its own checkout, and the repository it works on
(`GRAPH_REPO`, else the launch directory).
"""

from __future__ import annotations

import os
import pathlib

_LOOP = pathlib.Path(__file__).resolve().parents[2]


def loop() -> pathlib.Path:
    """Where this loop's own code lives — never the repository it builds."""
    return _LOOP


def repo() -> pathlib.Path:
    return pathlib.Path(os.environ.get("GRAPH_REPO") or pathlib.Path.cwd())

