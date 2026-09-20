"""A card sent for re-slicing is not written over a decision made while its gate
ran.

The gate that failed twice the same way ends the round with `needs_slice`. It is
a long call like any other, and the card can be dropped, held or rewritten while
it runs. The rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import loop_judge
from gates import GateResult
from test_loop import Fakes, loop_for, task
from workspace import Workspace

EXPECTED_TESTS = 1


def red_after_a_drop(book):
    """The gate comes back red, with the card dropped while it ran."""

    def run_gate(command, cwd, timeout=0, confine=True, **kwargs):
        book.set_status("T1", "dropped", refused_why="decided against")
        return GateResult(code=1, output="the gate failed again")

    return run_gate


class NeedsSliceCardMovedTest(unittest.TestCase):
    def test_a_card_dropped_while_the_failing_gate_ran_stays_dropped(self):
        loop, book, space = loop_for(task(), Fakes())
        with mock.patch.object(loop_judge, "run_gate", red_after_a_drop(book)), \
                mock.patch.object(Workspace, "needs_slice", lambda self, task_id: True):
            loop.run_task(book.task("T1"))
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
