"""Whatever a provider returns is untrusted input: a valid JSON answer of the
wrong shape is an outcome, never an exception. Split from `test_providers` at
the 200-line cap; the rig is imported from there."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import claude
from test_providers import fake

EXPECTED_TESTS = 7


class WrongShapeTest(unittest.TestCase):
    def test_valid_json_of_the_wrong_shape_is_an_outcome_not_an_exception(self):
        # It raised, and a live task then sat todo for the next turn to repeat.
        binary = fake("cat > /dev/null; echo '[\"a list, not an object\"]'")
        out = claude(binary, "prompt", account="work")
        self.assertEqual("malformed", out.kind)
        self.assertFalse(out.ok)


class NestedShapeTest(unittest.TestCase):
    def test_a_field_that_is_not_the_shape_it_claims_is_malformed_not_a_crash(self):
        for body in ('{"result": "ok", "usage": 42}', '{"result": "ok", "permission_denials": "none"}'):
            binary = fake(f"cat > /dev/null; echo '{body}'")
            out = claude(binary, "prompt", account="work")
            self.assertEqual("malformed", out.kind, body)

    def test_missing_token_counts_do_not_crash_the_read(self):
        """And they read as unknown, not as zero. A live task retries a refusal only
        when the answer proves it spent nothing, so a missing count must not look
        like proof of nothing."""
        binary = fake("cat > /dev/null; echo '" + '{"result": "done", "usage": {"input_tokens": null}}' + "'")
        out = claude(binary, "prompt", account="work")
        self.assertEqual("ok", out.kind)
        self.assertIsNone(out.tokens)

    def test_a_partial_usage_block_is_unknown_not_zero(self):
        """0 input tokens and no output count says nothing about what was spent,
        and a live task retries only on proof that nothing was."""
        body = ('{"is_error": true, "result": "at capacity", "total_cost_usd": 0,'
                ' "usage": {"input_tokens": 0}, "permission_denials": []}')
        out = claude(fake("cat > /dev/null; echo '" + body + "'"), "prompt", account="work")
        self.assertIsNone(out.tokens)
        self.assertFalse(out.unstarted)

    def test_missing_denials_are_unknown_not_none_given(self):
        body = ('{"is_error": true, "result": "at capacity", "total_cost_usd": 0,'
                ' "usage": {"input_tokens": 0, "output_tokens": 0}}')
        out = claude(fake("cat > /dev/null; echo '" + body + "'"), "prompt", account="work")
        self.assertEqual(-1, out.denials)
        self.assertFalse(out.unstarted)

    def test_a_json_boolean_is_not_zero_spend(self):
        """`isinstance(True, int)` is True in Python: `false` would read as zero,
        and zero spend is the proof a live action may be repeated."""
        body = ('{"is_error": true, "result": "at capacity", "total_cost_usd": false,'
                ' "usage": {"input_tokens": false, "output_tokens": 0}, "permission_denials": []}')
        out = claude(fake("cat > /dev/null; echo '" + body + "'"), "prompt", account="work")
        self.assertIsNone(out.cost)
        self.assertIsNone(out.tokens)
        self.assertFalse(out.unstarted)

    def test_a_refusal_carries_the_numbers_it_reports(self):
        """An expired session answers with zeroed usage; the error path used to drop
        them, so every refusal read as free whether it was or not."""
        body = ('{"is_error": true, "result": "Failed to authenticate", "total_cost_usd": 0,'
                ' "usage": {"input_tokens": 0, "output_tokens": 0}, "permission_denials": []}')
        out = claude(fake("cat > /dev/null; echo '" + body + "'"), "prompt", account="work")
        self.assertEqual("auth", out.kind)
        self.assertEqual(0, out.cost)
        self.assertEqual(0, out.tokens)
        self.assertTrue(out.unstarted)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
