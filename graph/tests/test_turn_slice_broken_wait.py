"""A wall whose dependencies are broken is skipped, never handed to the slicer.

`is_wall` reads the card's shape and never its `needs`, so a stuck CODE card
waiting on an id the backlog does not hold was offered to the slicer anyway.
Handing it over costs three paid rounds for nothing: the slicer's own law
refuses a plan whose external `needs` name an id that is not there. The plan
phase skips it and says which wait is broken, so the card is visible rather
than quietly re-sliced.

The rig is test_turn_slice's.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import slice_turn
from backlog_decision import broken_wait
from test_turn_slice import routed, router, space, tree_with

EXPECTED_TESTS = 3
WALL = {"id": "T1", "status": "needs_slice", "goal": "g", "files": ["a.py"],
        "gate": "false", "triage": "work", "needs": ["ghost"]}


class BrokenWallTest(unittest.TestCase):
    def test_a_wall_waiting_on_a_missing_card_is_not_handed_to_the_slicer(self):
        book = tree_with(dict(WALL))
        campaign = space()
        answer = unittest.mock.Mock(returncode=2, stdout="validation_refused: x", stderr="")
        route = router(answer)
        with routed(route):
            slice_turn.slice_pending(book, campaign)

        card = book.task("T1")
        self.assertEqual(["ghost"], list(card.get("needs") or []))
        self.assertTrue(broken_wait(card, book.tasks()), "the wait is not broken any more")
        for argv in route.slicer_calls:
            self.assertNotIn("--target", argv, "the slicer was asked to cut a broken wall")
        # uncharged: no slice round, no hold, no status write
        self.assertEqual("needs_slice", card.get("status"))
        self.assertIsNone(card.get("slices"))
        self.assertIsNone(card.get("blocked_by_human"))

    def test_the_skip_says_which_wait_is_broken(self):
        book = tree_with(dict(WALL))
        campaign = space()
        with routed(router(unittest.mock.Mock(returncode=0, stdout="", stderr=""))):
            slice_turn.slice_pending(book, campaign)
        said = [row.get("why") for row in campaign.events()
                if row.get("kind") == "slice_skipped" and row.get("task") == "T1"]
        self.assertEqual(1, len(said), campaign.events())
        self.assertIn(broken_wait(book.task("T1"), book.tasks()), said[0])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
