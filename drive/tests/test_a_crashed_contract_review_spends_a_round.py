"""A contract review that was paid for and did not answer costs the card a round.

The reviewer crashed, or answered something that was not a verdict: money was
spent and nothing on the card moved, so the next turn asked the same question
and paid again, for ever (astra round 4, finding 8). The round is the one the
in-place path already spends (`loop_judge_retry.back_in_place`), and at the cap
the build phase is done with it: it parks for the next plan phase. A reviewer
that was never
reached spends nothing, which `test_loop_faults` holds. The rig is `test_loop`'s.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from backlog_status import REBUILD_ROUNDS, spent_its_rounds
from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1


class CrashedContractReviewTest(unittest.TestCase):
    def test_a_review_that_crashes_every_turn_ends_at_the_round_cap(self):
        fakes = Fakes(review=[Outcome("crash", text="the reviewer died")])
        loop, book, _ = loop_for(task(), fakes)
        for _ in range(REBUILD_ROUNDS):
            self.assertEqual("harness", loop.run_task(book.task("T1")).state)
        row = book.task("T1")
        self.assertEqual(REBUILD_ROUNDS, int(row.get("rebuild_round") or 0))
        self.assertIn("crash", str(row.get("refused_why")))     # the cause TRIAGE reads
        self.assertTrue(spent_its_rounds(row))   # the build phase offers it no more


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
