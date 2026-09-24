"""A harness race, not an answered failure: the target can stop being a wall
between selection (`is_wall`, read at turn top) and the slicer's own re-read
(`slicer_law.assert_wall`, called again deep in `contracts.validate` a slow
planner call later — see SLICER.md). Split from `test_turn_slice` at the
200-line cap. The rig is `test_turn_slice`'s."""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import slice_turn
from test_turn_slice import routed, router, space, tree_with

EXPECTED_TESTS = 4

WALL = {"id": "T1", "status": "refused_contract", "goal": "g", "files": ["app.py"],
        "triage": "contract", "replans": 6, "refused_why": "the gate said why"}

# validation_refused's own form: contracts.validate's re-read, after a repair round.
PREFIXED_ANSWER = "validation_refused: T1 is not a stuck CODE card the slicer may take\n"
# slicer.py main()'s first guard, no model call yet: the bare ValueError text.
BARE_ANSWER = "T1 is not a stuck CODE card the slicer may take\n"
# contains the phrase, but is not the exact target-bound line — an ordinary
# answered refusal, charged like any other.
UNRELATED_ANSWER = ("validation_refused: a note observes that a card which "
                    "is not a stuck CODE card the slicer may take should "
                    "never reach this point, but the gate text is wrong too\n")


def _skipped_untouched(test, book, s):
    row = book.task("T1")
    test.assertEqual("refused_contract", row.get("status"))
    test.assertFalse(row.get("blocked_by_human"))
    test.assertEqual(0, int(row.get("slices") or 0))
    test.assertEqual("the gate said why", row.get("refused_why"))
    skipped = [e for e in s.events() if e.get("kind") == "slice_skipped"
              and e.get("task") == "T1"]
    test.assertEqual(1, len(skipped))
    test.assertIn("is not a stuck CODE card", skipped[0].get("why", ""))
    test.assertNotIn("slice_finished", [e.get("kind") for e in s.events()])


class WallRaceTest(unittest.TestCase):
    def test_the_prefixed_refusal_touches_nothing_and_is_skipped(self):
        book = tree_with(WALL)
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout=PREFIXED_ANSWER, stderr="")
        with routed(router(done)):
            slice_turn.slice_pending(book, s)
        _skipped_untouched(self, book, s)

    def test_the_bare_first_guard_refusal_touches_nothing_and_is_skipped(self):
        book = tree_with(WALL)
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout=BARE_ANSWER, stderr="")
        with routed(router(done)):
            slice_turn.slice_pending(book, s)
        _skipped_untouched(self, book, s)

    def test_unrelated_text_containing_the_phrase_is_charged_as_before(self):
        book = tree_with(WALL)
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout=UNRELATED_ANSWER, stderr="")
        with routed(router(done)):
            slice_turn.slice_pending(book, s)
        row = book.task("T1")
        self.assertEqual(1, int(row.get("slices") or 0))
        finished = [e for e in s.events() if e.get("kind") == "slice_finished"]
        self.assertEqual(1, len(finished))
        self.assertEqual("validation_refused", finished[0].get("state"))
        self.assertNotIn("slice_skipped", [e.get("kind") for e in s.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
