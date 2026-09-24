"""A retry policy cannot lift a person's hold on an unfinished card."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaigns import CODE, campaign
from plan_phase import requeue_faults

EXPECTED_TESTS = 3


class HumanHoldTest(unittest.TestCase):
    def test_a_persons_hold_survives_infrastructure_requeue(self):
        book, space = campaign([{**CODE, "id": "held", "status": "lane_failed",
                                 "triage": "harness", "blocked_by_human": True,
                                 "held_by": "person"}])
        before = book.task("held")
        requeue_faults(book, space)
        self.assertEqual(before, book.task("held"), "a human-held card must stay unchanged")
        self.assertEqual([], book.startable())

    def test_an_unheld_infrastructure_fault_is_still_retried_once(self):
        book, space = campaign([{**CODE, "id": "retry", "status": "lane_failed",
                                 "triage": "harness"}])
        self.assertEqual(1, requeue_faults(book, space))
        self.assertEqual("todo", book.task("retry")["status"])
        book.set_status("retry", "lane_failed", triage="harness")
        self.assertEqual(0, requeue_faults(book, space))

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
