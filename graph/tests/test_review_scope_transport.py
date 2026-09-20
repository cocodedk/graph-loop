"""Both reviewer transports carry the scoped answer intact to the diff boundary."""
from __future__ import annotations

import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import providers
import review
from prompts import diff_prompt
from review_scope import INSTRUCTION
from test_review_scope import DIFF, answer, finding

EXPECTED_TESTS = 4


class TransportTest(unittest.TestCase):
    def test_codex_keeps_the_whole_scoped_answer(self):
        text = answer([finding()], ["Independent observation"])
        with patch("review.codex_text", return_value=providers.Outcome("ok", text=text)):
            out = review._one_review("unused", "prompt", "unused", "", "medium", 1)
        self.assertEqual("REJECT", out.verdict)
        self.assertEqual(text, out.text)

    def test_claude_keeps_the_whole_scoped_answer(self):
        text = answer(observations=["Independent observation"])
        resource = types.SimpleNamespace(account="unused", model="unused")
        with patch("providers.claude", return_value=providers.Outcome("ok", text=text)):
            out = review._claude_review("prompt", resource, "medium", 1)
        self.assertEqual("ACCEPT", out.verdict)
        self.assertEqual(text, out.text)

    def test_an_extra_legacy_answer_cannot_rescue_a_scoped_answer(self):
        text = answer() + "\nREVIEW: ACCEPT"
        self.assertIsNone(review._read_review(text)[0])

    def test_numbering_carries_every_diff_line_and_the_shared_boundary(self):
        prompt = diff_prompt({"id": "T", "goal": "g", "files": ["a.py"],
                              "gate": "true", "done_when": "d"}, DIFF)
        self.assertIn("1: diff --git a/a.py b/a.py\n", prompt)
        self.assertIn("6: +two\n", prompt)
        self.assertIn(INSTRUCTION, prompt)


class CountTest(unittest.TestCase):
    def test_count(self):
        suite = unittest.TestLoader().discover(str(pathlib.Path(__file__).parent),
                                              pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, suite.countTestCases())


if __name__ == "__main__":
    unittest.main()
