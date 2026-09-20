"""`graph-goal.py cuts` — read or switch the state of a campaign's cut review."""

from __future__ import annotations

import pathlib
import sys

import where
from workspace import Workspace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "slicer"))

# ponytail: `_read` is private to cut_states; a public `history()` there would
# replace it, and this import with it.
from cut_states import (  # type: ignore[import-not-found]
    _read,
    load,
    switch,
)


def command_cuts(args) -> int:
    if args.state and not args.by:
        print("cuts: --state needs --by, so the history says who switched it", file=sys.stderr)
        return 2
    root = Workspace(args.workspace or where.campaign()).root
    if args.state:
        switch(root, args.state, args.by)
        print(args.state)
        return 0
    print(load(root))
    for entry in _read(root).get("history") or []:
        print(f"{entry['to']} by {entry['by']} at {entry['at']}")
    return 0
