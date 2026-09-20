"""The driver builds exactly the cards this turn's plan was told about.

The queue moves while a turn is in flight: a person holds a card between the
choice and the lanes. The held card is dropped and nothing is promoted into its
place, because the promoted card is one the slicer was never told to keep off.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import cardfile
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE / "lib"))

from keep import Keeper
from workspace import Workspace

_spec = importlib.util.spec_from_file_location("graph_goal", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 2


class Stop(Exception):
    """Ends the driver's loop at the one turn this test is about."""


def campaign(*names: str) -> types.SimpleNamespace:
    """An approved campaign whose tree backlog holds one CODE card per name."""
    root = pathlib.Path(tempfile.mkdtemp())
    backlog = root / "tree"
    for name in names:
        (backlog / name).mkdir(parents=True)
        (backlog / name / "molecule.md").write_text(cardfile.dump(
            {"goal": "g", "status": "todo", "files": [f"{name}.py"],
             "gate": "true", "done_when": "x"}), "utf-8")
    space = Workspace(root / "campaign").init(goal="the backlog", backlog=str(backlog))
    (space.root / "approved").write_text("approved\n", "utf-8")
    return types.SimpleNamespace(workspace=str(space.root), dry_run=False,
                                 lanes=3, max_tasks=0,
                                 idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)


class HeldAfterTheTurnOpensTest(unittest.TestCase):
    def test_a_card_held_after_the_turn_opened_is_not_built(self):
        # A person holds 01A while the turn is opening. The lanes read what is
        # startable AFTER that, so they build the rest and never 01A. Nothing
        # is planning beside them any more, so the cards behind it are safe to
        # promote — the slicer that was free to rewrite one belongs to the plan
        # phase now (`lib/plan_phase.py`).
        args = campaign("01A", "02B", "03C", "04D")
        took: list[str] = []
        opened = graph_goal.turn_opens

        def opens(space, book, args_, started_at, started=0):
            out = opened(space, book, args_, started_at, started)
            book.note("01A", blocked_by_human=True)
            return out

        def lanes(loop, book, space, tasks, turn_id=""):
            took.extend(row["id"] for row in tasks)
            raise Stop

        with unittest.mock.patch.object(graph_goal, "turn_opens", opens), \
             unittest.mock.patch.object(graph_goal, "run_lanes", lanes), \
             unittest.mock.patch.object(Keeper, "pending", lambda self: []), \
             unittest.mock.patch("publishing.behind", return_value=False), \
             self.assertRaises(Stop):
            graph_goal.command_run(args)
        self.assertNotIn("01A", took)
        self.assertEqual(["02B", "03C", "04D"], took)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
