"""A dry run says what the driver would do and ends nothing.

The honest ending is a WRITE: a durable receipt and an `ended_with_gaps` event
that every later turn reads as this campaign's terminal answer. A dry run
reached it — it stands down like any other turn where nothing is startable — so
looking at a campaign with `--dry-run` ended it, and the exit stayed 78 after
the card was finished for real (an independent review, finding 1).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
import unittest.mock

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))
import source_gap
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper
from workspace import Workspace

_spec = importlib.util.spec_from_file_location("graph_goal", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 1
LEFT = {"id": "T2", "status": "rejected", "goal": "prove the broker replays",
        "files": ["b.py"], "gate": "true", "needs": [],
        "refused_why": "the diff does not prove the replay"}


class DryRunEndingTest(unittest.TestCase):
    def test_a_dry_run_over_unfinished_work_ends_nothing(self):
        root = pathlib.Path(tempfile.mkdtemp())
        backlog = root / "b.yaml"
        backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": [dict(LEFT)]}))
        space = Workspace(root / "campaign").init(goal="the backlog", backlog=str(backlog))
        (space.root / "approved").write_text("approved\n", "utf-8")
        args = types.SimpleNamespace(workspace=str(space.root), dry_run=True,
                                     lanes=3, max_tasks=0,
                                     idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)

        with unittest.mock.patch.object(Keeper, "pending", lambda self: []), \
             unittest.mock.patch.object(graph_goal, "turn_opens", lambda *a: None), \
             unittest.mock.patch("publishing.behind", return_value=False):
            self.assertEqual(0, graph_goal.command_run(args))

        self.assertIsNone(source_gap.ended(space))
        self.assertEqual([], [row for row in space.events()
                              if row.get("kind") == "ended_with_gaps"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
