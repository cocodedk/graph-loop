"""What a reviewer crash should cost a card, and why one round is not one line.

the owner's interview decision of 18 September: "A card parks on its first failure;
the next plan phase slices it", replacing three rebuild rounds. The question it
left open was the reviewer CRASH: with one round, a lost review would park a
card whose work nobody ever judged.

That question is answered, and not by the counter. Both endings park the card,
and TRIAGE decides which recovery each one gets:

  the work failed        verdict `work`     -> a wall; the next plan phase re-slices it
  the review crashed     verdict `harness`  -> `requeue_faults` puts it back, once

`triage_signatures` already reads `review_unavailable` as a provider fault and
`plan_phase.requeue_faults` already puts those back once each, so the two
endings already have two recoveries. That is what this file holds.

What is NOT here is `REBUILD_ROUNDS = 1`, and the measurement is in
`backlog_status`: two paths increment that one counter, the work failing and the
machine failing, so setting it to one makes a usage limit part way through
reject the card and throw its paid work away. Saying what the owner decided needs
two counters, one per path.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog_status import REBUILD_ROUNDS, is_wall, spent_its_rounds
from triage_evidence import Ending
from triage_signatures import classify

EXPECTED_TESTS = 4


def parked(**more: object) -> dict:
    row = {"id": "T1", "status": "rejected", "files": ["app.py"], "rebuild_round": 1,
           "goal": "do it"}
    row.update(more)
    return row


class OneFailureParksIt(unittest.TestCase):
    def test_the_work_failing_makes_it_a_wall_for_the_next_plan_phase(self):
        self.assertTrue(is_wall(parked(triage="work", rebuild_round=REBUILD_ROUNDS)))

    def test_a_machine_fault_is_not_a_wall(self):
        # Re-cutting it would rewrite a card nobody found anything wrong with.
        self.assertFalse(is_wall(parked(triage="harness")))

    def test_a_lost_review_is_read_as_the_machine(self):
        card = parked()
        found = classify(Ending(task="T1", card=card, artifacts={}, gate_outputs=(),
                                events=({"kind": "review_unavailable", "task": "T1",
                                         "why": "the diff review did not happen (crash)"},
                                        {"kind": "rejected", "task": "T1",
                                         "why": "the diff review did not happen (crash)"})))
        self.assertEqual("harness", found.verdict)

    def test_a_card_that_never_failed_has_rounds_left(self):
        self.assertFalse(spent_its_rounds(parked(rebuild_round=0)))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
