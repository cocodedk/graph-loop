"""An account that cannot sign in, read from the credential it holds.

The first version read the answers on disk and went on complaining for hours
after the account was signed in again, because the refusals were still in its
window. A stale complaint teaches a reader to ignore the board.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from doctor_auth import check_auth

EXPECTED_TESTS = 6


def account(name: str, **oauth) -> tuple[str, str]:
    home = pathlib.Path(tempfile.mkdtemp())
    if oauth:
        (home / ".credentials.json").write_text(json.dumps({"claudeAiOauth": oauth}))
    return (name, str(home))


class AnAccountThatCannotSignIn(unittest.TestCase):
    def test_an_expired_credential_with_no_refresh_token_is_a_complaint(self):
        [complaint] = check_auth(homes=[account("work", expiresAt=(time.time() - 60) * 1000)])
        self.assertIn("work", complaint.what)
        self.assertIn("expired", complaint.what)
        self.assertIn("login", complaint.do)

    def test_a_refresh_token_means_it_can_renew_itself(self):
        self.assertEqual(check_auth(homes=[
            account("work", expiresAt=(time.time() - 60) * 1000, refreshToken="r")]), [])

    def test_a_credential_that_has_not_expired_is_well(self):
        self.assertEqual(check_auth(homes=[
            account("work", expiresAt=(time.time() + 3600) * 1000)]), [])

    def test_both_accounts_dead_are_named_together(self):
        [complaint] = check_auth(homes=[account("work", expiresAt=0),
                                        account("personal", expiresAt=0)])
        self.assertIn("work", complaint.what)
        self.assertIn("personal", complaint.what)

    def test_a_missing_or_unreadable_credential_is_not_a_complaint(self):
        """Guessing would cry wolf, and the calls say so soon enough."""
        self.assertEqual(check_auth(homes=[account("work")]), [])

    def test_a_credential_of_the_wrong_shape_is_not_a_complaint(self):
        home = pathlib.Path(tempfile.mkdtemp())
        (home / ".credentials.json").write_text('["not", "an object"]')
        self.assertEqual(check_auth(homes=[("work", str(home))]), [])


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
