"""A card waiting on something that cannot arrive is named, not left waiting.

"It waits on unsettled needs" would be a safe exclusion only while every need
can still land. A need the backlog does not hold, a ring of cards waiting on
each other, or a sliced parent cut into no pieces never settles, and a card
excluded for waiting on one of those is hidden from every actor for ever.

`broken_wait` names exactly the cards in the defect — the plan phase reads it
and skips them rather than slicing a card whose external needs are not there
(`slice_turn.slice_pending`). The healthy cards behind them keep waiting, or
one bad id would take a whole branch of the backlog out of the queue.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from backlog_decision import broken_wait

EXPECTED_TESTS = 7
CODE = {"goal": "g", "files": ["a.py"], "gate": "false", "triage": "work"}
ROWS = [
    {"id": "B1", "status": "todo", **CODE, "needs": ["ghost"]},
    {"id": "B2", "status": "todo", **CODE, "needs": ["B3"]},
    {"id": "B3", "status": "todo", **CODE, "needs": ["B2"]},
    {"id": "B4", "status": "sliced", **CODE, "needs": []},
    {"id": "B5", "status": "todo", **CODE, "needs": ["B1"]},
    # a ring through work that is already finished is not a ring at all
    {"id": "B6", "status": "todo", **CODE, "needs": ["B7"]},
    {"id": "B7", "status": "done", **CODE, "needs": ["B6"]},
    {"id": "B8", "status": "todo", **CODE, "needs": ["B9"]},
    {"id": "B9", "status": "dropped", **CODE, "needs": ["B8"]},
]
BY_ID = {row["id"]: row for row in ROWS}



class BrokenWaitTest(unittest.TestCase):
    def test_a_need_the_backlog_does_not_hold_is_named(self):
        self.assertEqual("it waits on ghost, which the backlog does not hold",
                         broken_wait(BY_ID["B1"], ROWS))

    def test_cards_that_wait_on_each_other_are_both_named(self):
        for task_id in ("B2", "B3"):
            with self.subTest(card=task_id):
                self.assertEqual("its needs lead back to itself",
                                 broken_wait(BY_ID[task_id], ROWS))

    def test_a_parent_sliced_into_no_pieces_is_named(self):
        self.assertIn("no pieces", broken_wait(BY_ID["B4"], ROWS))

    def test_a_healthy_card_behind_a_broken_one_keeps_waiting(self):
        """B5's own need exists and is not in a ring: B1 is the defect, and
        fixing B1 is what frees B5."""
        self.assertEqual("", broken_wait(BY_ID["B5"], ROWS))


class SettledWaitTest(unittest.TestCase):
    """A need that is finished ends the wait; what it happens to name after
    that is history. Walking through a settled card found B6 in its own needs
    and named a runnable card as broken — both terminal statuses do it,
    because both settle."""

    def test_a_ring_closed_by_a_done_card_is_not_a_ring(self):
        self.assertEqual("", broken_wait(BY_ID["B6"], ROWS))

    def test_a_ring_closed_by_a_dropped_card_is_not_a_ring(self):
        self.assertEqual("", broken_wait(BY_ID["B8"], ROWS))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
