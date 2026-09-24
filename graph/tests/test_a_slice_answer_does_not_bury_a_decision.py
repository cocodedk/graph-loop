"""A slicer answer does not write over a decision made while it planned.

A slice call runs for up to two hours. A drop, a hold or a rewrite decided in
them is newer than everything the answer was decided from, so charging the card
a slice round — or holding it for a person — buries that decision and brings
the card back (astra round 4, finding 2). The claims file already covers a lane
that took the card; nothing covered the decider or a person. The rig is
`test_turn_slice`'s.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import slice_turn
from test_turn_slice import routed, space, tree_with

EXPECTED_TESTS = 1

WALL = {"id": "T1", "status": "refused_contract", "goal": "g", "files": ["app.py"],
        "triage": "contract", "replans": 6, "refused_why": "the gate said why"}


def dropping(book, said: str):
    """Git answers plainly; the slicer refuses, with the card dropped in the
    minutes its call took."""

    def run(argv, **kwargs):
        if argv[0] == "git":
            return unittest.mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
        book.set_status("T1", "dropped", refused_why="decided against")
        return unittest.mock.Mock(returncode=2, stdout=said, stderr="")

    return run


class SliceAnswerCardMovedTest(unittest.TestCase):
    def test_a_card_dropped_while_the_slicer_planned_stays_dropped(self):
        book, campaign = tree_with(WALL), space()
        with routed(dropping(book, "validation_refused: the gate text escapes $")):
            slice_turn.slice_pending(book, campaign)
        row = book.task("T1")
        self.assertEqual("dropped", row.get("status"))
        self.assertEqual(0, int(row.get("slices") or 0))       # nobody judged this card
        self.assertIn("card_moved", [line.get("kind") for line in campaign.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
