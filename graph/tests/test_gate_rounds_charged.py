"""`gate_rounds` counts the rounds the card's OWN gate was charged for.

It is what a gate repair gives back (`triage_repairs`), so it has to be written
where the charge happens and nowhere else — a count kept anywhere but at the
charge drifts from it, and a refund is real money. A failed gate charges one; a
rejected diff is a finding about the work and charges none of the gate's. The
rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 3

ACCEPT = Outcome("ok", verdict="ACCEPT", text="ok")


class GateRoundsTest(unittest.TestCase):
    def test_a_failed_gate_charges_a_round_the_repair_can_give_back(self):
        fakes = Fakes(edit="still one\n")          # the gate never goes green
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertEqual(1, row["rebuild_round"])
        self.assertEqual(1, row["gate_rounds"])

    def test_a_rejected_diff_charges_a_round_that_is_not_the_gate_s(self):
        fakes = Fakes(review=[ACCEPT, Outcome("ok", verdict="REJECT", text="1. wrong line")])
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertEqual(1, row["rebuild_round"])
        self.assertNotIn("gate_rounds", row)


class LegacyRefundTest(unittest.TestCase):
    def test_a_refund_made_before_the_counter_existed_does_not_outlive_it(self):
        """The two counters are a pair. A card refunded while the refund still
        counted journal failures carries `gate_rounds_refunded` and no
        `gate_rounds`: a watermark describing charges this counter never saw.
        Left standing it is subtracted from every charge the card earns from
        here, and the card is never refunded again."""
        fakes = Fakes(edit="still one\n")          # the gate never goes green
        loop, book, _ = loop_for(task(gate_rounds_refunded=3), fakes)
        loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertEqual(1, row["gate_rounds"])                # the pair starts here
        self.assertNotIn("gate_rounds_refunded", row)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
