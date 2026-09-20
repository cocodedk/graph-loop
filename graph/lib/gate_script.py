"""Where a card's gate lives while its builder works.

Split out of `tools.py` at the 200-line cap; `tools` stays the front door and
re-exports both names.

OUTSIDE every worktree, on purpose. It was written into the worktree as
`.graph-gate.sh`, and the worktree diff is taken with intent-to-add, so the
script landed in the diff the reviewer reads and in the commit the keeper makes.
The first card that reached a reviewer said so: a file "added at the repo root,
outside the contract's file list" (2026-09-18). A path outside the tree cannot
reach either.

It is a copy, never the verdict: `loop_judge` runs the gate from the CARD, so a
builder that edits this script has edited its own scratch note.
"""

from __future__ import annotations

import pathlib
import tempfile

GATE_DIR = "graph-gates"


def gate_script_path(task: dict) -> str:
    """Where this card's gate script lives: one file per card, outside every
    worktree, overwritten each round. The id is the card's own, which the
    slicer already holds to a safe name; a stray `/` in one would otherwise
    write into a directory of its own choosing."""
    return str(pathlib.Path(tempfile.gettempdir()) / GATE_DIR
               / f"{str(task.get('id') or 'card').replace('/', '-')}.sh")


def write_gate_script(task: dict) -> str:
    """Put this card's gate where the builder may run it, byte for byte, and say
    where. Nothing for a card with no gate."""
    gate = str(task.get("gate") or "")
    if not gate.strip():
        return ""
    path = pathlib.Path(gate_script_path(task))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(gate, "utf-8")
    path.chmod(0o700)
    return str(path)
