"""Recovery settles a parent on the child that was reviewed, and no other.

The publication bound the parent's contract (`sliced_from_contract`) and said
nothing about the child's own: a goal, a gate or an atom edited after the folder
landed was settled into the backlog as though a reviewer had read it (astra's
round-4 finding 9, "bind reviewed child contents too"). The publish receipt
digests the plan inside the folder — the fields the slicer's own answer declares
— so an edited child is stale, while a card that has merely STARTED is not.
The rig lives in `test_tree`.
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
from tree import CardMoved, publish, roll_forward

EXPECTED_TESTS = 4


class BoundChildTest(unittest.TestCase):
    def setUp(self):
        """The child folder landed and the parent's own write did not."""
        self.root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        self.root.mkdir()
        self.book = Backlog(self.root)
        publish(self.root, task("large"))
        publish(self.root, task("small", atoms=[atom("schema", 1), atom("reader", 2)]),
                "large")
        self.book.set_status("large", "needs_slice", needs=[], refused_why="too broad")

    def test_a_child_edited_since_it_was_reviewed_does_not_settle_its_parent(self):
        self.book.note("small.schema", gate="true")     # a gate nobody reviewed
        with self.assertRaises(CardMoved):
            roll_forward(self.root, "large")
        self.assertEqual("needs_slice", self.book.task("large")["status"])

    def test_a_child_whose_work_has_started_still_settles_its_parent(self):
        """Status is not the plan: an atom a lane picked up is the reviewed
        molecule, still, and retiring it would throw away work in flight."""
        self.book.set_status("small.schema", "live_call_open")
        self.assertEqual("small", roll_forward(self.root, "large"))
        self.assertEqual("sliced", self.book.task("large")["status"])

    def test_a_dependency_deleted_from_an_atom_does_not_settle_its_parent(self):
        """The waits ARE the plan: an atom that no longer waits for the card
        that makes what it uses starts before it, and the reviewer read the
        molecule with that wait in it (an independent review, finding 3)."""
        publish(self.root, task("extra"))
        publish(self.root, task("waiting"))
        self.book.set_status("waiting", "needs_slice", needs=[], refused_why="too broad")
        publish(self.root, task("cut", atoms=[{**atom("step", 1), "needs": ["extra"]}]),
                "waiting")
        self.book.set_status("waiting", "needs_slice", needs=[],   # the parent's write is undone
                             refused_why="too broad")
        self.book.note("cut.step", needs=[])       # the wait is gone; nobody reviewed that

        with self.assertRaises(CardMoved):
            roll_forward(self.root, "waiting")
        self.assertEqual("needs_slice", self.book.task("waiting")["status"])

    def test_the_waits_the_tree_writes_back_are_not_an_edited_plan(self):
        """`backlog_tree` copies a molecule's own waits into its first stage's
        files on the next write, and the stage numbers are the rest: reading
        either as an edit would retire a molecule nobody touched."""
        publish(self.root, task("extra"))
        publish(self.root, task("inherits"))
        self.book.set_status("inherits", "needs_slice", needs=["extra"],
                             refused_why="too broad")
        publish(self.root, task("cut", atoms=[atom("schema", 1), atom("reader", 2)]),
                "inherits")
        self.book.set_status("inherits", "needs_slice", needs=["extra"],
                             refused_why="too broad")     # the parent's write is undone
        self.book.set_status("extra", "done")      # any write normalises every file

        self.assertEqual("cut", roll_forward(self.root, "inherits"))
        self.assertEqual("sliced", self.book.task("inherits")["status"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
