"""Refused contracts recover from judge gaps, key spelling and attempt context."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from contract import contract_prompt
from prompts import diff_prompt
from replan import prompt_for, replan, replan_until_planned
from test_keep import repo
from test_replan import GOOD, answer, book_with

EXPECTED_TESTS = 7


class ReplanStallsTest(unittest.TestCase):
    def test_replan_and_contract_review_close_a_judge_gap_with_a_gate_probe(self):
        task = book_with().task("T1")
        for make in (prompt_for, contract_prompt):
            with self.subTest(prompt=make.__name__):
                prompt = make(task)
                for phrase in ("concrete bypass", "frozen judge test", "executed probe",
                               "beside the project's tests", "project's test command",
                               "trap on exit", "exactly the named case", "bypass fails the gate",
                               "files unchanged", "gate text", "greps or regexes",
                               "never ask for the judge to change"):
                    self.assertIn(phrase, prompt)
        self.assertIn("Refuse that gap only while the gate lacks this probe", contract_prompt(task))

    def test_diff_review_does_not_reopen_the_accepted_contract(self):
        prompt = diff_prompt(book_with().task("T1"), "diff")
        self.assertIn("contract (goal, gate, done_when, files) is accepted", prompt)
        self.assertIn("is not under review", prompt)
        self.assertIn("Refuse only for what the change does or fails to do under that contract", prompt)
        self.assertIn("weakness of the gate or the criteria is an observation, not a refusal", prompt)

    def test_rewrite_keys_are_normalised_before_validation_and_storage(self):
        for spelling in ("done when", "Done-When", " DONE WHEN "):
            with self.subTest(spelling=spelling):
                book = book_with()
                text = GOOD.replace("done_when:", f"'{spelling}':").replace("goal:", "' Goal ':")
                out = replan(book, book.task("T1"), lambda prompt, text=text: answer(text))
                self.assertTrue(out.rewritten, out.why)
                self.assertEqual("a.py says two", book.task("T1")["done_when"])
                self.assertEqual(1, book.task("T1")["replans"])
                self.assertNotIn(spelling, book.task("T1"))

    def test_unknown_keys_still_refuse_and_the_next_prompt_quotes_the_refusal(self):
        book = book_with()
        prompts = []
        answers = iter([GOOD + "' Still-Unknown ': value\n", GOOD])

        def planner(prompt):
            prompts.append(prompt)
            return answer(next(answers))

        out = replan_until_planned(book, book.task("T1"), planner)
        self.assertTrue(out.rewritten, out.why)
        self.assertEqual(2, len(prompts))
        self.assertIn("this one also wrote still_unknown", prompts[1])
        self.assertIn("the gate passes on a comment", prompts[1])

    def test_attempt_changes_are_named_and_marked_unlanded(self):
        root = pathlib.Path(repo())
        (root / "a.py").write_text("uncommitted work\n")
        (root / "new test.py").write_text("untracked work\n")
        (root / "staged.py").write_text("staged work\n")
        subprocess.run(["git", "-C", str(root), "add", "staged.py"], check=True)
        for field in ("rebuild_from", "worktree"):
            with self.subTest(field=field):
                prompt = prompt_for(book_with(**{field: str(root)}).task("T1"))
                self.assertIn("['a.py', 'new test.py', 'staged.py']", prompt)
                self.assertIn("not landed on the campaign branch", prompt)
                self.assertIn("cannot prove this card is already complete", prompt)
                self.assertIn("judge completion against the campaign branch tip", prompt)

    def test_a_missing_attempt_tree_does_not_claim_no_files_changed(self):
        root = pathlib.Path(repo()) / "gone"
        prompt = prompt_for(book_with(rebuild_from=str(root)).task("T1"))
        self.assertIn("unknown (attempt worktree unavailable)", prompt)

    def test_long_failure_evidence_survives_replan_history(self):
        why = "FAIL: missing behaviour\n" + "details\n" * 140
        book = book_with(refused_why=why)
        out = replan(book, book.task("T1"), lambda prompt: answer(GOOD))
        self.assertTrue(out.rewritten, out.why)
        self.assertEqual([why.strip()], book.task("T1")["replan_history"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        self.assertEqual(EXPECTED_TESTS + 1,
                         unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases())


if __name__ == "__main__":
    unittest.main()
