"""A turn is counted once however many lanes it ran.

Split from `test_watchdog` at the 200-line cap; the rig is imported from there."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from test_watchdog import space
from watchdog import check

EXPECTED_TESTS = 3


class ParallelTurnTest(unittest.TestCase):
    def test_three_lanes_of_one_turn_are_one_turn(self):
        here = space()
        for task in ("T1", "T2", "T3"):
            here.event("released", task=task, turn="turn-1")
        self.assertFalse(check(here).stuck)          # one turn, not three
        for n in (2, 3):
            for task in ("T1", "T2"):
                here.event("released", task=task, turn=f"turn-{n}")
        self.assertTrue(check(here).stuck)           # three turns finished nothing


    def test_a_turn_that_accepted_work_is_never_counted_as_fruitless(self):
        here = space()
        here.event("accepted", task="T1", turn="turn-1", commit="abc")
        for task in ("T2", "T3"):
            here.event("released", task=task, turn="turn-1")     # its siblings
        for n in (2, 3):
            here.event("released", task="T9", turn=f"turn-{n}")
        self.assertFalse(check(here).stuck)                      # two fruitless turns, not three


class StuckIgnoresFailedGatesTest(unittest.TestCase):
    def test_turns_that_only_failed_their_gates_are_still_fruitless(self):
        # Each round's real shape (lib/loop_steps.py, lib/loop_judge.py): an
        # answered build call, recorded before its gate even runs, then the
        # gate's own step fails. That answered call alone used to reset the
        # stuck window, so three fruitless turns in a row never tripped it —
        # the loop looked alive.
        here = space()
        for task in ("T1", "T2", "T3"):
            here.attempt(task, account="work", kind="ok")
            with here.step(task, "gate") as note:
                note(passed=False)
            here.attempt(task, account="gate", kind="ok", failed_gate=True)
            here.event("released", task=task)
        self.assertTrue(check(here).stuck)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
