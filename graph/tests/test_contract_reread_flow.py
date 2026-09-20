"""A gate reviewed inside its round is not reviewed again on the rebuild."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1


class OneReviewPerContractTest(unittest.TestCase):
    def test_a_gate_reviewed_before_it_ran_is_not_reviewed_a_second_time(self):
        # gate_reviewed_first says the replan's gate was read before red-first
        # ran it; the round must then be review, build, review — the contract
        # digest recorded by that review is what keeps the second one away
        fakes = Fakes()
        loop, book, _ = loop_for(task(gate_reviewed_first=True), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(["review", "build:work", "review"], fakes.calls)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
