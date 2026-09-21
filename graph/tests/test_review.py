"""One review call: the rung it runs at, and how its answer is read.

Split from `test_providers` at the 200-line cap; the rig is imported from there."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import codex
from test_providers import fake, result

EXPECTED_TESTS = 17


class ReviewShapeTest(unittest.TestCase):
    """The reviewer answers in JSON too, so the log parses without guessing."""

    def test_a_json_review_is_read_by_its_flags(self):
        binary = fake("""echo '{"review": "REJECT", "accept": false, """
                      """"findings": ["the gate proves nothing", "two ideas"]}'""")
        out = codex(binary, "review this")
        self.assertEqual("REJECT", out.verdict)
        self.assertIn("the gate proves nothing", out.text)
        self.assertIn("two ideas", out.text)

    def test_a_reviewer_that_answers_the_old_way_is_still_understood(self):
        binary = fake("echo 'REVIEW: ACCEPT'; echo '1. fine'")
        out = codex(binary, "review this")
        self.assertEqual("ACCEPT", out.verdict)


class ReviewEffortTest(unittest.TestCase):
    def test_a_review_runs_at_the_rung_it_was_given_and_never_max(self):
        import providers
        with tempfile.NamedTemporaryFile("r", delete=False) as handle:
            os.environ["OUT"] = handle.name
            providers.codex(fake("echo \"$@\" > $OUT; echo 'REVIEW: ACCEPT'"), "p", effort="medium")
            argv = pathlib.Path(handle.name).read_text()
        self.assertIn('model_reasoning_effort="medium"', argv)
        self.assertNotIn("max", argv)
        self.assertEqual("medium", providers.REVIEW_EFFORT)   # the default, when no task decides


class CodexTest(unittest.TestCase):
    def test_the_reviewer_is_sol_at_the_default_effort(self):
        binary = fake("echo \"$@\" > $OUT; echo 'REVIEW: ACCEPT'")
        with tempfile.NamedTemporaryFile("r", delete=False) as handle:
            os.environ["OUT"] = handle.name
            out = codex(binary, "review this")
            argv = pathlib.Path(handle.name).read_text()
        self.assertIn("--model gpt-6-astra", argv)
        self.assertIn('model_reasoning_effort="medium"', argv)
        self.assertEqual("ACCEPT", out.verdict)

    def test_a_reject_carries_the_findings(self):
        binary = fake("echo 'REVIEW: REJECT'; echo '1. fix this line'")
        out = codex(binary, "review this")
        self.assertEqual("REJECT", out.verdict)
        self.assertIn("fix this line", out.text)

    def test_a_review_without_a_verdict_line_is_malformed(self):
        binary = fake("echo 'I think it is fine'")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)


class UntrustedVerdictTest(unittest.TestCase):
    """The reply is untrusted input (CLAUDE.md): a `review`/`accept` pair that
    disagrees, or a `findings` that is not the promised list, is not a verdict
    to trust — malformed, the same as no verdict at all."""

    def test_review_and_accept_disagreeing_is_malformed(self):
        binary = fake("""echo '{"review": "ACCEPT", "accept": false, "findings": []}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_findings_that_is_not_a_list_is_malformed(self):
        binary = fake("""echo '{"review": "ACCEPT", "accept": true, "findings": "none"}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_a_missing_accept_key_is_malformed(self):
        binary = fake("""echo '{"review": "ACCEPT", "findings": []}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_an_extra_key_is_malformed(self):
        binary = fake("""echo '{"review": "ACCEPT", "accept": true, """
                      """"findings": [], "note": "extra"}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_a_non_string_finding_is_malformed(self):
        binary = fake("""echo '{"review": "ACCEPT", "accept": true, "findings": [1, "ok"]}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_more_than_three_findings_is_malformed(self):
        binary = fake("""echo '{"review": "ACCEPT", "accept": true, """
                      """"findings": ["a", "b", "c", "d"]}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_a_review_word_outside_the_two_literals_is_malformed(self):
        # lowercase, not the literal "ACCEPT" the prompt declares — wider than
        # the shape asked for, so not accepted just because it upper-cases to it.
        binary = fake("""echo '{"review": "accept", "accept": true, "findings": []}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_two_legacy_verdicts_that_disagree_are_malformed(self):
        # The old `REVIEW:` line was read forwards, so the FIRST word won and a
        # reviewer that said ACCEPT and then REJECT was recorded as an accept.
        binary = fake("echo 'REVIEW: ACCEPT'; echo 'REVIEW: REJECT'")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_a_reviewer_that_exited_badly_gave_no_verdict(self):
        # A lesson about the harness: key on the exit code, never on matched text.
        binary = fake("echo 'REVIEW: ACCEPT'; exit 3")
        out = codex(binary, "review this")
        self.assertEqual("crash", out.kind)
        self.assertIsNone(out.verdict)

    def test_a_well_formed_accept_still_parses(self):
        binary = fake("""echo '{"review": "ACCEPT", "accept": true, "findings": []}'""")
        out = codex(binary, "review this")
        self.assertEqual("ACCEPT", out.verdict)
        self.assertEqual("ok", out.kind)


class ClaudeFallbackExitTest(unittest.TestCase):
    """The fallback reviewer is read the same way. `out.ok` was the whole guard
    and `providers.claude` never looked at the exit code, so a call that died
    while printing a well-formed answer came back as an accepted review."""

    def test_a_fallback_reviewer_that_exited_badly_gave_no_verdict(self):
        import review  # here, not at the top: `providers` must start the pair
        answer = result(result="REVIEW: ACCEPT")
        binary = fake(f"cat > /dev/null; echo '{answer}'; exit 3")
        with unittest.mock.patch.dict(os.environ, {"GRAPH_CLAUDE": binary}):
            out = review._claude_review("judge this", review.resources.Resource(
                "claude", "work", "claude-opus-5"), "high", 60)
        self.assertIsNone(out.verdict)
        self.assertNotEqual("ok", out.kind)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
