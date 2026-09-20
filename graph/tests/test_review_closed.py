"""One verdict, read as a closed answer: no contradiction gets through.

Round-2 finding 1 of astra's review (2026-09-08). The verdict used to be read
format by format — the JSON answer first, and the old `REVIEW:` line only when
no JSON line parsed — so an answer that said both things was read as whichever
format was looked at first. Split from `test_review.py`, which is near its cap.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import codex
from test_providers import fake

EXPECTED_TESTS = 6

ACCEPT = '{"review": "ACCEPT", "accept": true, "findings": []}'


class ContradictionTest(unittest.TestCase):
    """Two verdicts that disagree are no verdict, whatever shape they arrive in."""

    def test_a_json_accept_and_a_legacy_reject_disagree(self):
        # The JSON line was read first and returned, so the `REVIEW:` line
        # below it was never seen and the answer passed as an accept.
        binary = fake(f"echo '{ACCEPT}'; echo 'REVIEW: REJECT'")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_a_key_given_twice_is_not_the_shape_asked_for(self):
        # `json.loads` keeps the last of two same-named keys, so a reviewer
        # could write `review` twice and the loop read whichever it kept.
        binary = fake("""echo '{"review": "REJECT", "review": "ACCEPT", """
                      """"accept": true, "findings": []}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_a_broken_answer_does_not_fall_back_to_an_earlier_one(self):
        # The scan walked backwards and skipped a JSON line it could not read,
        # so a good ACCEPT above a broken REJECT was the verdict it returned.
        binary = fake(f"""echo '{ACCEPT}'; """
                      """echo '{"review": "reject", "accept": false, "findings": ["x"]}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_an_answer_that_was_cut_off_is_not_skipped(self):
        # A reviewer whose REJECT was truncated leaves a line that opens an
        # object and never closes it. That was no candidate at all, so the
        # ACCEPT above it stood as the verdict (Codex, round 2 finding 1).
        binary = fake(f"echo '{ACCEPT}'; "
                      """echo '{"review": "REJECT", "accept": false, "findings": ["cut'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)

    def test_an_escaped_key_is_the_key_it_decodes_to(self):
        # `\\u0072eview` decodes to `review`. The key used to be looked for in
        # the raw line, so this answer was not read at all.
        binary = fake("""echo '{"\\u0072eview": "REJECT", "accept": false, """
                      """"findings": ["the gate proves nothing"]}'""")
        out = codex(binary, "review this")
        self.assertEqual("REJECT", out.verdict)
        self.assertIn("the gate proves nothing", out.text)

    def test_an_escaped_key_reject_under_an_accept_still_disagrees(self):
        binary = fake(f"echo '{ACCEPT}'; "
                      """echo '{"\\u0072eview": "REJECT", "accept": false, "findings": []}'""")
        out = codex(binary, "review this")
        self.assertEqual("malformed", out.kind)
        self.assertIsNone(out.verdict)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
