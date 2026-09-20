"""Every review-belt member that was asked lands in the record — refusals too."""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import review
from providers import Outcome
from resources import Resource

EXPECTED_TESTS = 3


class BeltAttemptsTest(unittest.TestCase):
    def test_a_refusal_then_a_success_records_both_real_accounts(self):
        belt = [Resource(agent="codex", model="m1", account="first"),
                Resource(agent="codex", model="m2", account="second")]
        answers = [Outcome("limit", text="at capacity"),
                   Outcome("ok", verdict="ACCEPT", text="fine", cost=0.0, tokens=42)]
        seen = []
        with unittest.mock.patch.object(review.resources, "belt", return_value=belt), \
             unittest.mock.patch.object(review, "_one_review", side_effect=answers):
            out = review.codex("codex", "judge this",
                               attempt=lambda kind, account, cost, tokens, text:
                               seen.append((kind, account, cost, tokens, text)))
        self.assertEqual("ACCEPT", out.verdict)
        self.assertEqual([("limit", "first", None, None, "at capacity"),
                          ("ok", "second", 0.0, 42, "fine")], seen)


class StdinPromptTest(unittest.TestCase):
    def test_a_whole_source_prompt_travels_on_stdin_not_argv(self):
        big = "x" * 2_000_000
        seen = {}

        def run(argv, stdin, env, timeout):
            seen.update(argv=argv, stdin=stdin)
            return unittest.mock.Mock(   # returncode: a verdict needs a call that finished
                returncode=0, stdout='{"review": "ACCEPT", "accept": true, "findings": []}',
                stderr="")
        # the call itself lives in `provider_codex` now; the review only reads it
        with unittest.mock.patch("provider_codex._run", side_effect=run):
            out = review._one_review("codex", big, "m1", "", "medium", 60)
        self.assertEqual("ACCEPT", out.verdict)
        self.assertEqual(big, seen["stdin"])
        self.assertEqual("-", seen["argv"][-1])
        self.assertTrue(all(len(part) < 1000 for part in seen["argv"]))


class ClaudeSpendTest(unittest.TestCase):
    def test_a_normalized_claude_verdict_keeps_its_spend(self):
        answered = Outcome("ok", text="REVIEW: ACCEPT", cost=0.25, tokens=999)
        resource = Resource(agent="claude", model="m", account="work")
        with unittest.mock.patch.object(review, "claude", create=True), \
             unittest.mock.patch("providers.claude", return_value=answered):
            out = review._claude_review("judge", resource, "medium", 60)
        self.assertEqual(("ok", "ACCEPT", 0.25, 999),
                         (out.kind, out.verdict, out.cost, out.tokens))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
