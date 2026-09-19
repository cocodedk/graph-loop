"""Adding an account is a line of data, not an edit to the loop.

The name-to-configuration mapping lived in three places: the order in
loop_types, an `account == "personal"` branch in providers, and a second copy in
the doctor. A third account could not be added without editing code, and that
is the whole reason the loop has more than one.
"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import accounts

EXPECTED_TESTS = 7


class TheAccountTable(unittest.TestCase):
    def test_the_default_configuration_is_removed_not_set_empty(self):
        """An empty CLAUDE_CONFIG_DIR points at a config with no login."""
        env, drop = accounts.environment("work")
        self.assertEqual({}, env)
        self.assertEqual(("CLAUDE_CONFIG_DIR",), drop)

    def test_an_account_with_its_own_configuration_sets_it(self):
        with unittest.mock.patch.dict(os.environ, {"DRIVE_ACCOUNTS": "work,second=~/second"}):
            env, drop = accounts.environment("second")
        self.assertEqual((), drop)
        self.assertTrue(env["CLAUDE_CONFIG_DIR"].endswith("/second"))
        self.assertNotIn("~", env["CLAUDE_CONFIG_DIR"])

    def test_a_third_account_needs_no_code(self):
        with unittest.mock.patch.dict(os.environ, {"DRIVE_ACCOUNTS": "work,second=/cfg/second,spare=/cfg/spare"}):
            self.assertEqual(("work", "second", "spare"), accounts.names())
            env, drop = accounts.environment("spare")
            self.assertTrue(env["CLAUDE_CONFIG_DIR"].endswith("/cfg/spare"))
            self.assertEqual((), drop)

    def test_an_unknown_account_is_refused_not_silently_defaulted(self):
        """A typo used to fall through to the work account and spend it."""
        with self.assertRaises(KeyError):
            accounts.environment("typo")
        with self.assertRaises(KeyError):
            accounts.home("typo")

    def test_every_account_says_where_its_credentials_live(self):
        for name in accounts.names():
            self.assertTrue(str(accounts.home(name)).startswith("/"))

    def test_an_empty_setting_falls_back_to_the_one_account_we_ship(self):
        with unittest.mock.patch.dict(os.environ, {"DRIVE_ACCOUNTS": "  "}):
            self.assertEqual(("work",), accounts.names())


class ExhaustionFollowsTheCredential(unittest.TestCase):
    def test_two_names_on_one_directory_run_out_together(self):
        """What runs out is the session, not the label: a limit on the first name
        would otherwise leave the second looking fresh."""
        import resources
        with unittest.mock.patch.dict(os.environ, {"DRIVE_ACCOUNTS": "one=/cfg/same,two=/cfg/same"}):
            belt = resources.belt("build")
            first = next(r for r in belt if r.account == "one")
            second = next(r for r in belt if r.account == "two")
            spent = resources.Exhausted()
            spent.note(first, "limit")
            self.assertTrue(spent.skip(second), "the same credential was asked again")


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
