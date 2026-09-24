"""The words a session that has expired actually answers with.

The loop filed them as a crash for a whole night, so the builder's account walk
treated an expired work session as an unexplained failure instead of a reason
to try the other account.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import AUTH_MARKS

EXPECTED_TESTS = 2
EXPIRED = "Failed to authenticate: OAuth session expired and could not be refreshed"


class AnExpiredSessionIsAnAuthFailure(unittest.TestCase):
    def test_the_real_words_match_a_mark(self):
        self.assertTrue(any(mark in EXPIRED.lower() for mark in AUTH_MARKS),
                        f"no mark in AUTH_MARKS matches {EXPIRED!r}")

    def test_the_real_json_answer_matches_a_mark(self):
        answer = json.dumps({"type": "result", "is_error": True, "result": EXPIRED})
        self.assertTrue(any(mark in answer.lower() for mark in AUTH_MARKS))


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
