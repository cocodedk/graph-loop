"""A backlog and a campaign, for the tests that need both.

Not a test: the shared setup several of them would otherwise each write out,
the way `tmp_root` is shared.
"""

from __future__ import annotations

import pathlib
import tempfile

import yaml  # type: ignore[import-untyped]
from backlog import Backlog
from workspace import Workspace

CODE = {"goal": "read the journal", "files": ["a.py"], "gate": "grep -q two a.py",
        "done_when": "a.py says two", "needs": [], "note": ""}
STUCK = {"id": "T1", "status": "rejected", "triage": "unknown", "rebuild_round": 3,
         "refused_why": "the reviewer never answered", **CODE}


def campaign(rows: list[dict], root: str = "") -> tuple[Backlog, Workspace]:
    """A backlog of these cards and a campaign that remembers nothing yet."""
    path = pathlib.Path(root or tempfile.mkdtemp()) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"tasks": rows}), "utf-8")
    return (Backlog(path),
            Workspace(tempfile.mkdtemp()).init(goal="prove the board", backlog=str(path)))


def card(book: Backlog, task_id: str = "T1") -> dict:
    """One card, or a plain failure: a test that hands `None` on gets its error
    three frames later, about something else."""
    found = book.task(task_id)
    if found is None:
        raise KeyError(f"{task_id} is not in {book.path}")
    return found
