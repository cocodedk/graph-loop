"""A card decided against after the turn chose it is not run by the lane.

The turn picks its cards, then each lane claims. Between those two moments a
person or another writer can drop the card, hold it, or rewrite its contract —
and a lane that runs it anyway finishes work somebody had settled. The rig is
`test_lanes`'s.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from loop_types import TaskOutcome
from test_lanes import book_of
from turn import run_lanes
from workspace import Workspace

EXPECTED_TESTS = 2


class Keeping:
    """A builder that finishes its card, as the keeper does."""

    def __init__(self, book):
        self.book = book
        self.seen: list[str] = []

    def run_task(self, task):
        self.seen.append(task["id"])
        self.book.set_status(task["id"], "done")
        return TaskOutcome("done", "")


class DroppedAfterPickingTest(unittest.TestCase):
    def test_a_card_dropped_after_the_turn_chose_it_stays_dropped(self):
        book = book_of("T1")
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        picked = book.tasks()
        book.set_status("T1", "dropped", refused_why="decided against")
        loop = Keeping(book)
        ran, outside = run_lanes(loop, book, space, picked)
        self.assertEqual([], loop.seen)                     # never built
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertEqual({}, space.running())               # never claimed
        self.assertFalse(outside)
        self.assertIn("lane_skipped", [row.get("kind") for row in space.events()])
        self.assertEqual(1, ran)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
