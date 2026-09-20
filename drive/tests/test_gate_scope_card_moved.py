"""A gate's scope fault is not written over a decision made while it ran.

`gate_left_its_lane` runs after every gate execution: the gate moved HEAD, or it
wrote outside the card's files. Both end the round with `out_of_scope` on the
card — and the gate is a long call, so the card may have been dropped or held
while it ran. The fault is still recorded; the card is not rewritten. The rig
lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import loop_evidence
import loop_judge_retry
from test_loop import Fakes, loop_for, task
from worktree import HeadMoved, Worktree

EXPECTED_TESTS = 2


def red_after_a_drop(book):
    """The gate proves red, with the card dropped while it ran."""

    def prove_red(command, cwd, expect="", **kwargs):
        book.set_status("T1", "dropped", refused_why="decided against")
        return True, "proved red"

    return prove_red


class GateScopeCardMovedTest(unittest.TestCase):
    def setUp(self):
        self.loop, self.book, self.space = loop_for(task(), Fakes())
        self.dropped = mock.patch.object(loop_evidence, "prove_red",
                                         red_after_a_drop(self.book))

    def moved(self) -> bool:
        return "card_moved" in [row.get("kind") for row in self.space.events()]

    def test_a_gate_that_wrote_outside_its_files_leaves_the_decided_card_alone(self):
        with self.dropped, mock.patch.object(loop_judge_retry, "changed_outside",
                                             lambda *a, **k: ["b.py"]):
            self.loop.run_task(self.book.task("T1"))
        self.assertEqual("dropped", self.book.task("T1")["status"])
        self.assertTrue(self.moved())

    def test_a_gate_that_moved_head_leaves_the_decided_card_alone(self):
        with self.dropped, mock.patch.object(Worktree, "on_base",
                                             mock.Mock(side_effect=HeadMoved("moved"))):
            self.loop.run_task(self.book.task("T1"))
        self.assertEqual("dropped", self.book.task("T1")["status"])
        self.assertTrue(self.moved())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
