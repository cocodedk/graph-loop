"""A diff longer than the reviewer can read whole is refused, not cut.

Codex GPT-5 review, 2026-09-02: `diff_prompt` cut the diff at 60,000 characters
silently, so the reviewer judged a truncated diff and could ACCEPT what it
never saw. The loop-level behaviour (the round ends rejected, the reviewer is
never called) is in `test_loop_diff_limit.py`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from prompts import DIFF_LIMIT, DiffTooLarge, diff_prompt

EXPECTED_TESTS = 2


def task(**extra) -> dict:
    row = {"id": "T1", "goal": "g", "files": ["a.py"], "gate": "true", "done_when": "x"}
    row.update(extra)
    return row


class DiffLimitTest(unittest.TestCase):
    def test_a_diff_one_character_over_the_limit_is_refused_not_cut(self):
        oversized = "x" * (DIFF_LIMIT + 1)
        with self.assertRaises(DiffTooLarge) as raised:
            diff_prompt(task(), oversized)
        self.assertEqual(DIFF_LIMIT + 1, raised.exception.size)
        self.assertEqual(DIFF_LIMIT, raised.exception.limit)

    def test_a_diff_at_the_limit_is_shown_whole(self):
        exact = "x" * DIFF_LIMIT
        prompt = diff_prompt(task(), exact)
        self.assertIn(exact, prompt)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
