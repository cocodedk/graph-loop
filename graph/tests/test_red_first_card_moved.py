"""A red-first refusal is not written over a decision made while the gate ran.

Proving the gate red runs shell that can take minutes, and another writer can
settle the card in them. `green_already` and `unprovable` both end the round with
a status write, and neither asked whether the card was still the one the round
started from. The rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import loop_evidence
from gates import GREEN_ALREADY
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 2


def green_after_a_drop(book):
    """The gate comes back green, with the card dropped while it ran."""

    def prove_red(command, cwd, expect="", **kwargs):
        book.set_status("T1", "dropped", refused_why="decided against")
        return False, GREEN_ALREADY

    return prove_red


class RedFirstCardMovedTest(unittest.TestCase):
    def test_a_lasting_gate_edited_while_the_gate_ran_is_not_overwritten(self):
        loop, book, space = loop_for(task(gate_until_kept=True), Fakes())

        def edited(*args):
            book.note("T1", gate_when_kept="test -f a.py")
            return False, GREEN_ALREADY

        with mock.patch.object(loop_evidence, "prove_red", edited):
            loop.run_task(book.task("T1"))
        self.assertEqual("todo", book.task("T1")["status"])
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])

    def test_a_card_dropped_while_the_gate_ran_stays_dropped(self):
        loop, book, space = loop_for(task(), Fakes())
        with mock.patch.object(loop_evidence, "prove_red", green_after_a_drop(book)):
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
