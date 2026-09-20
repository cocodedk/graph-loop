"""A kept coverage record is not a fresh one: the slicer has to have proved it.

Codex's review: a deleted approved source makes the slicer exit 2 out of its own
validation, before it ever looks at the coverage record — and a checkout it
cannot cut means the slicer is never started at all. The record survives both,
matches the backlog it was written for, and `stand_down` read it as a finish.

So the driver asks two things now, and both are needed: the source-gap slicer
finished successfully since THIS driver announced itself, and the record it left
still stands for the backlog. Companion to test_driver_uncovered.py, which
covers the record going stale.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE / "lib"))
sys.path.append(str(HERE.parent / "slicer"))

import where
from backlog import Backlog
from keep import Keeper
from slice_outcome import record_outcome
from slice_turn import slice_pending
from slicer_state import close  # type: ignore[import-not-found]
from workspace import Workspace

_spec = importlib.util.spec_from_file_location("graph_goal", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 2
SOURCE = "README.md"          # a real file of the loop's own checkout, read only for its bytes


def campaign() -> tuple[Workspace, Backlog]:
    """An approved campaign whose empty tree backlog already carries an accepted
    coverage record for its one declared source."""
    root = pathlib.Path(tempfile.mkdtemp())
    tree = root / "tree"
    tree.mkdir()
    space = Workspace(root / "campaign").init(goal="the backlog", backlog=str(tree))
    (space.root / "approved").write_text("approved\n", "utf-8")
    space.event("sources_declared", sources=[SOURCE])
    repo = where.loop()
    close(tree, [repo / SOURCE], "accepted", repo, [])
    return space, Backlog(tree)


def run(space: Workspace) -> int:
    args = types.SimpleNamespace(workspace=str(space.root), dry_run=False,
                                 lanes=3, max_tasks=0,
                                 idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)
    with unittest.mock.patch.object(Keeper, "pending", lambda self: []), \
         unittest.mock.patch.object(graph_goal, "turn_opens", lambda *a: None), \
         unittest.mock.patch("publishing.behind", return_value=False):
        return graph_goal.command_run(args)


class UnprovenTest(unittest.TestCase):
    def test_a_source_the_slicer_could_not_find_does_not_finish_the_campaign(self):
        """`slicer.py` validates its approved sources before anything else and
        exits 2 when one is gone — the record it wrote for that source is never
        looked at, so it stands. Written here by `record_outcome`, the only
        thing that turns a slicer exit into a campaign record."""
        space, book = campaign()
        record_outcome(book, space, "the sources", None,
                       f"approved source does not exist: {where.loop() / SOURCE}", 2)

        self.assertEqual(1, run(space))

    def test_a_checkout_the_loop_could_not_cut_does_not_finish_the_campaign(self):
        """No clean checkout of the campaign branch, so `slice_pending` records
        a skip and the slicer is never started."""
        space, book = campaign()
        elsewhere = pathlib.Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", "-b", "main", str(elsewhere)],
                       capture_output=True, check=True)
        with unittest.mock.patch.object(where, "repo", return_value=elsewhere), \
             unittest.mock.patch.object(where, "branch", return_value="campaign/never-made"):
            slice_pending(book, space)

        skipped = [row for row in space.events() if row.get("kind") == "slice_skipped"]
        self.assertTrue(skipped, "the checkout failure must be on the record")
        self.assertEqual(1, run(space))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
