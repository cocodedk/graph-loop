"""A task the loop cannot finish must never be handed back for ever.

Written after the first real campaign spun: a contract refusal left the task
`todo`, the picker returned it on the next turn, and the same review was paid for
again every two minutes. Every ending a task can have now writes a status the
picker will not offer again.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 6


class SpinTest(unittest.TestCase):
    def test_a_refused_contract_is_marked_and_never_offered_again(self):
        fakes = Fakes(review=[Outcome("ok", verdict="REJECT",
                                      text="1. the gate proves nothing")])
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual("refused_contract", book.task("T1")["status"])
        self.assertIn("proves nothing", book.task("T1")["refused_why"])
        self.assertEqual([], book.startable())

    def test_a_rejected_diff_is_offered_again_until_its_rounds_are_spent(self):
        reject = Outcome("ok", verdict="REJECT", text="1. wrong line")
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              reject, reject, reject, reject])
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        # one rejection is a finding list: the task is offered again
        self.assertEqual("todo", book.task("T1")["status"])
        self.assertEqual(["T1"], [row["id"] for row in book.startable()])
        loop.run_task(book.task("T1"))
        loop.run_task(book.task("T1"))
        # the third rejection spends the rounds: a person now, never re-offered
        self.assertEqual("rejected", book.task("T1")["status"])
        self.assertEqual([], book.startable())

    def test_a_gate_that_is_already_green_is_marked_rather_than_retried(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(gate="true"), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual("green_already", book.task("T1")["status"])
        self.assertEqual([], book.startable())

    def test_one_failed_gate_leaves_the_task_open_for_a_second_try(self):
        fakes = Fakes(edit="still one\n")
        loop, book, space = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual("todo", book.task("T1")["status"])
        self.assertFalse(space.needs_slice("T1"))

    def test_the_second_identical_failure_asks_for_a_slice_instead(self):
        fakes = Fakes(edit="still one\n")
        loop, book, space = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        loop.run_task(book.task("T1"))
        self.assertTrue(space.needs_slice("T1"))
        self.assertEqual("needs_slice", book.task("T1")["status"])
        self.assertEqual([], book.startable())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
