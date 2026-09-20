"""A decision made WHILE the slicer planned is not published over.

`assert_wall` catches a hold raised before the planner answers. The progress
review runs after it, and a contract edit is not a status change at all: the
publish itself is the last chance to see that the card the slicer planned is
no longer the card on disk. The rig lives in `test_tree`.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
DRIVE_LIB = HERE.parent / "drive" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DRIVE_LIB))
from backlog import Backlog  # type: ignore[import-not-found]
from test_tree import task
from tree import CardMoved, publish

EXPECTED_TESTS = 2


class CardMovedTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        self.root.mkdir()
        self.book = Backlog(self.root)
        publish(self.root, task("large"))
        self.book.set_status("large", "needs_slice", refused_why="too broad")
        self.started = self.book.task("large")

    def test_a_hold_raised_while_the_slicer_planned_stops_the_publish(self):
        self.book.note("large", blocked_by_human=True)      # a person, mid-slice
        with self.assertRaises(CardMoved):
            publish(self.root, task("small"), "large", self.started)
        row = self.book.task("large")
        self.assertTrue(row["blocked_by_human"])            # the hold stands
        self.assertEqual("needs_slice", row["status"])      # not settled under it

    def test_a_contract_edited_while_the_slicer_planned_stops_the_publish(self):
        self.book.note("large", goal="build large, narrowed by hand")
        with self.assertRaises(CardMoved):
            publish(self.root, task("small"), "large", self.started)
        row = self.book.task("large")
        self.assertEqual("build large, narrowed by hand", row["goal"])
        self.assertEqual("needs_slice", row["status"])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
