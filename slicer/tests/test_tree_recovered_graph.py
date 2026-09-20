"""Recovery validates the graph that is on disk, not an empty answer.

Finishing an interrupted publish asks the same cycle question the fresh publish
asks — but it was asked with the recovery's own stub molecule (no atoms), so the
check REBUILT the stored child's waits from nothing and erased them. A circle
running through the child's own atoms was invisible: `large` waits for `small`,
`small` for `small.step`, `small.step` for `other`, and `other` for `large`, and
recovery settled the parent into it. The rig lives in `test_tree`.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
GRAPH_LIB = HERE.parent / "graph" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GRAPH_LIB))
from backlog import Backlog  # type: ignore[import-not-found]
from test_tree import atom, task
from tree import publish, roll_forward

EXPECTED_TESTS = 1


class RecoveredGraphTest(unittest.TestCase):
    def test_a_circle_through_the_stored_child_stops_the_recovery(self):
        root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        root.mkdir()
        book = Backlog(root)
        publish(root, task("large"))
        publish(root, task("small", atoms=[{**atom("step", 1), "needs": ["other"]}]), "large")
        book.set_status("large", "needs_slice", needs=[], refused_why="too broad")
        publish(root, task("other", needs=["large"]))     # the circle closes here
        with self.assertRaisesRegex(ValueError, "circle"):
            roll_forward(root, "large")
        row = book.task("large")
        self.assertEqual("needs_slice", row["status"])    # refused before the parent changed
        self.assertEqual([], row["needs"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
