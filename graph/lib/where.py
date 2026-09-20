"""Where this loop is pointed. Everything else imports these answers.

The loop's logic is generic; only four places are not — the loop's own
checkout, the repository it works on, the campaign directory it remembers in,
and the backlog it works from. The last three resolve from an environment
variable first, so pointing the whole loop at other work is:

    export GRAPH_REPO=/path/to/the/repo/being/built
    export GRAPH_CAMPAIGN=$GRAPH_REPO/scratchpad/graph-campaigns/current
    export GRAPH_BACKLOG=$GRAPH_REPO/vault

`GRAPH_REPO` defaults to the directory the loop is run from, because the loop
lives in its own repository now and can never guess the one it is working on.
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


def campaign() -> pathlib.Path:
    return pathlib.Path(os.environ.get("GRAPH_CAMPAIGN")
                        or repo() / "scratchpad" / "graph-campaigns" / "current")


def backlog() -> pathlib.Path:
    return pathlib.Path(os.environ.get("GRAPH_BACKLOG")
                        or repo() / "vault")


def branch() -> str:
    return os.environ.get("GRAPH_BRANCH") or "campaign/graph"
