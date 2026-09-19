"""The slicer's own retry budget: a refused_contract wall reaches the slicer
only with its REPLAN budget spent (`is_wall`), so a slicer failure must not
spend that same budget again — it costs one of the slicer's own `slices` instead, capped
separately at `MAX_SLICES`. Taking an unheld target already at the cap means
something released the hold, whatever wrote it, and resets the count. Split
from `test_turn_slice` at the 200-line cap. The rig is `test_turn_slice`'s."""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import slice_turn
from test_turn_slice import routed, router, space, tree_with

EXPECTED_TESTS = 6

# A refused-contract wall: is_wall requires replans already AT the human cap
# (backlog_status.is_wall) before the slicer ever sees it.
WALL = {"id": "T1", "status": "refused_contract", "goal": "g", "files": ["app.py"],
        "triage": "contract", "replans": 2, "refused_why": "the gate said why"}


class OneFailureTest(unittest.TestCase):
    def test_a_wall_keeps_its_status_and_spends_a_slice_not_a_replan(self):
        book = tree_with(WALL)
        s = space()
        done = unittest.mock.Mock(
            returncode=2, stdout=r"validation_refused: the gate text escapes $ as \$", stderr="")
        with routed(router(done)):
            slice_turn.slice_pending(book, s)
        row = book.task("T1")
        self.assertEqual("refused_contract", row.get("status"))
        self.assertFalse(row.get("blocked_by_human"))
        self.assertEqual(1, int(row.get("slices") or 0))
        self.assertEqual(2, int(row.get("replans") or 0))       # untouched


class CappedTest(unittest.TestCase):
    def test_the_third_failure_holds_the_card_and_alerts(self):
        book = tree_with(WALL)
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout="validation_refused: x", stderr="")
        route = router(done)
        with routed(route):
            slice_turn.slice_pending(book, s)          # slices -> 1, still a wall
            slice_turn.slice_pending(book, s)          # slices -> 2, still a wall
            slice_turn.slice_pending(book, s)          # slices -> 3, capped and held
        self.assertEqual(3, len(route.slicer_calls))
        row = book.task("T1")
        self.assertTrue(row.get("blocked_by_human"))
        self.assertEqual(3, int(row.get("slices") or 0))
        self.assertEqual(2, int(row.get("replans") or 0))       # still untouched
        said = [line for line in s.alerts() if "a person decides" in str(line)]
        self.assertEqual(1, len(said))


class HandEditTest(unittest.TestCase):
    def test_a_stale_cap_with_no_hold_gets_one_fresh_attempt(self):
        # a person's direct yaml edit dropped blocked_by_human but never
        # touched slices -- whatever released it, is_wall still selects the
        # card, and taking it resets the slicer's own stale cap first
        book = tree_with({**WALL, "slices": 3})
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout="validation_refused: x", stderr="")
        route = router(done)
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertEqual(1, len(route.slicer_calls))
        row = book.task("T1")
        self.assertFalse(row.get("blocked_by_human"))
        self.assertEqual(1, int(row.get("slices") or 0))


class NeedsPersonClearsSlicesTest(unittest.TestCase):
    def test_a_needs_person_answer_clears_the_slice_count(self):
        # the card is held either way; the count has served its purpose
        book = tree_with({**WALL, "slices": 2})
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout="needs_person: ask a human", stderr="")
        with routed(router(done)):
            slice_turn.slice_pending(book, s)
        row = book.task("T1")
        self.assertTrue(row.get("blocked_by_human"))
        self.assertNotIn("slices", row)


class SuccessPersistsResetTest(unittest.TestCase):
    def test_a_successful_attempt_after_a_stale_cap_leaves_no_slices_behind(self):
        # the take-time reset must reach disk on its own -- a success writes
        # nothing else, so an in-memory-only reset would leave the old count
        # sitting there for the next time this card becomes a wall
        book = tree_with({**WALL, "slices": 3})
        s = space()
        done = unittest.mock.Mock(returncode=0, stdout="published: T1.fix", stderr="")
        with routed(router(done)):
            slice_turn.slice_pending(book, s)
        row = book.task("T1")
        self.assertNotIn("slices", row)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
