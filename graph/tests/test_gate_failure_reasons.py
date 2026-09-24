"""A runner's footer must not hide the test failure from retries or slicing."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from gates import GateResult, prove_red
from keep import CombinedGateFailed, Keeper
from test_keep import repo
from test_loop import Fakes, loop_for, task
from worktree import Worktree

EXPECTED_TESTS = 5
FOOTER = "runner details\n" * 75 + "BUILD FAILED in 1s\n"


def output(name: str) -> str:
    return "setup\n" * 400 + f"FAIL: {name}\n" + FOOTER


class GateFailureReasonsTest(unittest.TestCase):
    def test_retry_and_slice_compare_test_names_before_a_shared_footer(self):
        first, second = output("test_first_case"), output("test_second_case")
        fakes = Fakes(edit=first)
        loop, book, space = loop_for(task(gate="cat a.py; false"), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual(first[-2000:], out.why)
        self.assertEqual([first[-2000:]], book.task("T1")["rejections"])
        fakes.edit = second
        loop.run_task(book.task("T1"))
        self.assertIn(first[-2000:], fakes.prompts[1])
        self.assertFalse(space.needs_slice("T1"))
        self.assertEqual("todo", book.task("T1")["status"])
        fakes.edit = first
        loop.run_task(book.task("T1"))
        self.assertTrue(space.needs_slice("T1"))
        self.assertEqual("needs_slice", book.task("T1")["status"])
        self.assertEqual(first[-2000:], book.task("T1")["refused_why"])
        failures = [row["why"] for row in space.events()
                    if row["kind"] == "failed" and row.get("step") == "gate"]
        self.assertEqual([first[-2000:], second[-2000:], first[-2000:]], failures)

    def test_the_last_retry_keeps_the_wider_reason_on_the_card_and_event(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(gate="cat a.py; false"), fakes)
        for name in ("test_first", "test_second", "test_third"):
            fakes.edit = output(name)
            loop.run_task(book.task("T1"))
        self.assertEqual("rejected", book.task("T1")["status"])
        self.assertEqual(fakes.edit[-2000:], book.task("T1")["refused_why"])
        rejected = [row for row in space.events() if row["kind"] == "rejected"]
        self.assertEqual(fakes.edit[-2000:], rejected[-1]["why"])

    def test_red_first_reasons_keep_the_same_two_thousand_character_tail(self):
        text = output("test_red_first")
        for kind, expect, proved in (("ran", "test_red_first", True),
                                     ("ran", "absent", False), ("timeout", "", False)):
            with self.subTest(kind=kind, expect=expect):
                with mock.patch("gates.run_gate", return_value=GateResult(1, text, kind=kind)):
                    ok, why = prove_red("unused", "unused", expect=expect)
                self.assertEqual(proved, ok)
                self.assertTrue(why.endswith(text[-2000:]))

    def test_red_first_refusal_writers_do_not_cut_the_reason_back_to_four_hundred(self):
        why = output("test_wrong_failure")[-2000:]
        loop, book, space = loop_for(task(), Fakes())
        with mock.patch("loop_evidence.prove_red", return_value=(False, why)):
            loop.run_task(book.task("T1"))
        self.assertEqual(why, book.task("T1")["refused_why"])
        refused = [row for row in space.events() if row["kind"] == "refused"]
        self.assertEqual(why, refused[-1]["why"])

    def test_a_combined_gate_failure_keeps_the_test_name_and_wider_tail(self):
        root = repo()
        keeper = Keeper(root, "campaign/test")
        tree = Worktree(root, "T1", keeper.tip()).create()
        text = output("test_combined")
        (pathlib.Path(tree.path) / "a.py").write_text(text)
        with self.assertRaises(CombinedGateFailed) as caught:
            keeper.keep("T1", tree.path, "change", files=["a.py"], gates=["cat a.py; false"])
        self.assertIn(text[-2000:].strip(), str(caught.exception))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        self.assertEqual(EXPECTED_TESTS + 1,
                         unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases())


if __name__ == "__main__":
    unittest.main()
