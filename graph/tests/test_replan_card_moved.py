"""A person's decision made WHILE the planner runs outlives the rewrite.

The planner call takes minutes. A hold raised in that window, or a contract
edited in it, is newer than everything the rewrite was decided from — storing
the rewrite would clear the hold or bury the edit. The rig lives in
`test_replan`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from replan import replan
from test_replan import GOOD, answer, book_with

EXPECTED_TESTS = 3


class CardMovedTest(unittest.TestCase):
    def test_a_hold_raised_while_the_planner_ran_is_not_cleared(self):
        book = book_with()
        started = book.task("T1")

        def planner(prompt):
            book.note("T1", blocked_by_human=True)   # a person, mid-call
            return answer(GOOD)

        out = replan(book, started, planner)
        self.assertFalse(out.rewritten)
        row = book.task("T1")
        self.assertTrue(row["blocked_by_human"])            # the hold stands
        self.assertEqual("refused_contract", row["status"])  # not requeued

    def test_a_contract_edited_while_the_planner_ran_is_not_overwritten(self):
        book = book_with()
        started = book.task("T1")

        def planner(prompt):
            book.note("T1", goal="make a.py say two, and only that")
            return answer(GOOD)

        out = replan(book, started, planner)
        self.assertFalse(out.rewritten)
        self.assertEqual("make a.py say two, and only that", book.task("T1")["goal"])

    def test_a_card_that_moved_costs_no_round(self):
        """Nobody judged the contract as it now stands: charging a replan for
        that would spend the card's two rounds on a race."""
        book = book_with()
        started = book.task("T1")

        def planner(prompt):
            book.note("T1", blocked_by_human=True)
            return answer(GOOD)

        replan(book, started, planner)
        self.assertNotIn("replans", book.task("T1"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
