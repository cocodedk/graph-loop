"""Recovery does not settle a parent that was rewritten after its child landed.

`roll_forward` finishes the one publish whose parent update was interrupted. It
found the child by lineage alone — `sliced_from` names the parent — and lineage
survives a rewrite: a card whose goal, gate, files or waits were changed since
that child was planned would be marked `sliced` by a molecule planned for the
older contract, and nobody would ever read the new one. The child publication
binds the parent's contract instead, and recovery refuses when it differs. The
rig lives in `test_tree`.
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
from tree import CardMoved, publish, roll_forward

EXPECTED_TESTS = 2


class StaleChildTest(unittest.TestCase):
    def setUp(self):
        """The child folder landed and the parent's own write did not."""
        self.root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        self.root.mkdir()
        self.book = Backlog(self.root)
        publish(self.root, task("large"))
        publish(self.root, task("small"), "large")
        self.book.set_status("large", "needs_slice", needs=[], refused_why="too broad")

    def test_a_parent_rewritten_since_its_child_landed_is_not_settled_by_it(self):
        self.book.note("large", goal="build large, narrowed by hand")
        with self.assertRaises(CardMoved):
            roll_forward(self.root, "large")
        row = self.book.task("large")
        self.assertEqual("needs_slice", row["status"])       # still the slicer's to cut
        self.assertNotIn("small", row["needs"] or [])        # and the old child is not its work

    def test_a_parent_nobody_touched_is_still_settled_by_its_interrupted_child(self):
        self.assertEqual("small", roll_forward(self.root, "large"))
        row = self.book.task("large")
        self.assertEqual("sliced", row["status"])
        self.assertEqual(["small"], row["needs"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
