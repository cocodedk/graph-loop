"""Before a rule is written twice, the builder is told to find the module that
already follows it, and the reviewer is told a second copy is a finding.

Three services read the same assertion key three ways on 2026-08-30; two were
right and the kill door was wrong. Nothing in the loop asked for reuse."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from prompts import build_prompt, diff_prompt

EXPECTED_TESTS = 2


def task(**extra) -> dict:
    row = {"id": "T1", "goal": "g", "files": ["a.py"], "gate": "true", "done_when": "x"}
    row.update(extra)
    return row


class ReuseTest(unittest.TestCase):
    def test_the_builder_is_told_to_follow_what_already_exists(self):
        prompt = build_prompt(task())
        self.assertIn("Where a module here already follows the rule you need, follow that module", prompt)
        self.assertIn("rather than writing a second copy", prompt)
        self.assertIn("goes in your final line, because a refactor", prompt)   # report, never refactor

    def test_the_reviewer_reports_only_a_second_copy_introduced_by_this_change(self):
        prompt = diff_prompt(task(), "diff")
        self.assertIn("this change duplicates it", prompt)
        self.assertIn("name the module it should have followed", prompt)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
