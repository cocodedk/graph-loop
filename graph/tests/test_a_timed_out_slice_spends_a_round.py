"""A slice that ran to its ceiling spends one of the slicer's own rounds.

The 7200 s ceiling is not an outage: the slicer read the question and made its
own paid planner calls before the clock ran out. Counted with the refusals
nobody answered, it charged nothing and the next turn spent two more hours on
the same card, for ever (astra round 4, finding 8). A resource that refused
before reading — `planner_unavailable`, `review_unavailable` — still spends
nothing, and so does a card decided while the slicer planned. The rig is
`test_turn_slice`'s.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import slice_turn
from test_turn_slice import routed, space, tree_with

EXPECTED_TESTS = 1

WALL = {"id": "T1", "status": "refused_contract", "goal": "g", "files": ["app.py"],
        "triage": "contract", "replans": 2, "refused_why": "the gate said why"}


def out_of_time(argv, **kwargs):
    """Git answers plainly; the slicer never comes back."""
    if argv[0] == "git":
        return unittest.mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
    raise subprocess.TimeoutExpired(argv, 7200)


class TimedOutSliceTest(unittest.TestCase):
    def test_a_slice_that_ran_out_of_time_costs_a_slice_round(self):
        book, campaign = tree_with(WALL), space()
        with routed(out_of_time):
            slice_turn.slice_pending(book, campaign)
        self.assertEqual(1, int(book.task("T1").get("slices") or 0))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
