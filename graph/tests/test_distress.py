"""The builder answers in JSON with fixed flags, and the loop reads the flags.

The owner, 2026-08-28: deterministic flags, not prose. Anything else is UNCLEAR, and
UNCLEAR always tells a person.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from distress import read_result

EXPECTED_TESTS = 15

DONE = '{"result": "DONE", "blocked": false, "needs_person": false, "why": ""}'
BLOCKED = ('{"result": "BLOCKED", "blocked": true, "needs_person": true, '
           '"why": "the fix needs a verb the agent does not have"}')


class FlagTest(unittest.TestCase):
    def test_done_is_read_from_the_flags(self):
        out = read_result("I changed the seed and the gate passes.\n" + DONE)
        self.assertEqual(("DONE", False, False), (out.state, out.blocked, out.needs_a_person))

    def test_blocked_carries_its_reason(self):
        out = read_result(BLOCKED)
        self.assertEqual(("BLOCKED", True, True), (out.state, out.blocked, out.needs_a_person))
        self.assertIn("verb the agent does not have", out.why)

    def test_partial_is_a_state_of_its_own_and_tells_a_person(self):
        out = read_result('{"result": "PARTIAL", "blocked": false, '
                          '"needs_person": true, "why": "two of three checks pass"}')
        self.assertEqual("PARTIAL", out.state)
        self.assertTrue(out.needs_a_person)

    def test_the_last_json_line_is_the_one_that_counts(self):
        out = read_result(BLOCKED + "\nthinking again...\n" + DONE)
        self.assertEqual("DONE", out.state)

    def test_a_result_word_we_do_not_know_is_unclear(self):
        out = read_result('{"result": "MOSTLY", "why": "hmm"}')
        self.assertEqual("UNCLEAR", out.state)
        self.assertIn("MOSTLY", out.why)

    def test_prose_instead_of_json_is_unclear(self):
        out = read_result("I finished, I think. RESULT: DONE")
        self.assertEqual("UNCLEAR", out.state)
        self.assertTrue(out.needs_a_person)

    def test_broken_json_is_unclear_rather_than_believed(self):
        out = read_result('{"result": "DONE", "why": }')
        self.assertEqual("UNCLEAR", out.state)

    def test_words_of_distress_without_a_line_are_still_caught(self):
        out = read_result("Permission denied on every edit, so I stopped.")
        self.assertEqual("UNCLEAR", out.state)
        self.assertIn("permission denied", out.why)

    def test_a_done_that_asks_for_a_person_parks_instead_of_finishing(self):
        # The flag was written and never read, so a builder could say it had
        # finished and ask for a person in the same line, and the card passed.
        out = read_result('{"result": "DONE", "blocked": false, '
                          '"needs_person": true, "why": "someone must check the seed"}')
        self.assertEqual("BLOCKED", out.state)
        self.assertTrue(out.needs_a_person)

    def test_a_denial_mentioned_beside_a_done_flag_is_still_done(self):
        out = read_result("Bash was denied twice; I read the files another way.\n" + DONE)
        self.assertEqual("DONE", out.state)

    def test_a_done_that_sets_blocked_parks_instead_of_finishing(self):
        # `blocked` was written by the prompt and read by nobody, so a builder
        # could say it had finished and that it was stopped in the same line.
        out = read_result('{"result": "DONE", "blocked": true, '
                          '"needs_person": false, "why": "the gate needs a key"}')
        self.assertEqual("BLOCKED", out.state)
        self.assertTrue(out.needs_a_person)

    def test_a_key_given_twice_is_not_a_result(self):
        # `json.loads` keeps the last of two same-named keys, so a builder
        # could write `result` twice and the loop read whichever it kept.
        out = read_result('{"result": "BLOCKED", "result": "DONE", "blocked": false, '
                          '"needs_person": false, "why": ""}')
        self.assertEqual("UNCLEAR", out.state)

    def test_a_broken_last_line_does_not_fall_back_to_an_earlier_done(self):
        out = read_result(DONE + '\n{"note": 1}')
        self.assertEqual("UNCLEAR", out.state)

    def test_a_result_line_that_was_cut_off_is_not_skipped(self):
        # A builder whose BLOCKED was truncated leaves a line that opens an
        # object and never closes it. That was no result line at all, so the
        # DONE above it was the answer the loop recorded (Codex, round 2).
        out = read_result(DONE + '\n{"result": "BLOCKED", "blocked": true, "why": "cut')
        self.assertEqual("UNCLEAR", out.state)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
