"""A lane's own failure is not parked over a decision made while it ran.

The lane takes the card, builds for an hour, and dies. `lane_failed` says what
happened to the lane — but the card may have been dropped or held in that hour
by another writer, and parking it there buries that decision. The rig is
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
from test_lanes import FakeLoop, book_of
from turn import run_lanes
from workspace import Workspace

EXPECTED_TESTS = 1


class DyingLoop(FakeLoop):
    """A lane whose card is dropped while it builds, and which then dies."""

    def __init__(self, book):
        super().__init__()
        self.book = book

    def run_task(self, task):
        self.book.set_status("T1", "dropped", refused_why="decided against")
        raise ZeroDivisionError("the lane died after the card was decided")


class LaneFailureCardMovedTest(unittest.TestCase):
    def test_a_card_dropped_while_the_lane_ran_stays_dropped(self):
        book = book_of("T1")
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        run_lanes(DyingLoop(book), book, space, book.tasks())
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertTrue(space.alerts())            # the lane's death is still heard
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
