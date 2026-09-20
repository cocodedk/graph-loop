"""A planner call that was paid for and did not answer costs the card a replan.

`replan_refused: the planner did not answer (crash)` stood in the campaign
record turn after turn (events-0009.jsonl:20,32): the call crashed, ownership
and counters stayed where they were, and the next turn asked the same question
and paid again. An answered — or half-answered — call spends its round, and at
the cap the card is nobody's to rewrite: it parks for the next plan phase. A resource that refused
before reading spends nothing, which `test_replan`'s outage case holds (astra
round 4, finding 8). The rig is `test_replan`'s.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from backlog_decision import can_replan
from providers import Outcome
from replan import MAX_REPLANS, replan_until_planned
from test_replan import book_with

EXPECTED_TESTS = 1


class CrashedPlannerTest(unittest.TestCase):
    def test_a_planner_that_crashes_every_call_ends_at_the_replan_cap(self):
        book = book_with()
        out = replan_until_planned(book, book.task("T1"),
                                   lambda prompt: Outcome("crash", text="the planner died"))
        self.assertFalse(out.rewritten)
        row = book.task("T1")
        self.assertEqual(MAX_REPLANS, int(row.get("replans") or 0))
        self.assertFalse(can_replan(row))       # nothing in a build turn rewrites it again


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
