"""A project names the one account its lean runs spend: `## account` in its profile, a label the
machine's GRAPH_ACCOUNTS maps to a login. The loop's default login can be someone's work account,
and a personal project's builds must not land on it: fifteen of them did (2026-09-28)."""

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import accounts
import alert_email
import lean
import lean_git
import lean_run
import tmp_root  # noqa: F401
from test_keep import repo
from test_lean import PROFILE_BASE
from workspace import Workspace

EXPECTED_TESTS = 5


class ProjectAccount(unittest.TestCase):
    def setUp(self):
        self.repo = repo()
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text(
            "Mechanics are in [profile-test.md](profile-test.md).\n")
        self.profile = pathlib.Path(self.repo) / "profile-test.md"
        self.profile.write_text(PROFILE_BASE)
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        self.spec.write_text("Restyle the Log screen.\n")
        self.mails, self.spent = [], []
        for patched in (mock.patch.dict(os.environ, {"GRAPH_ACCOUNTS": "work,personal=/tmp/second"}),
                        mock.patch.object(lean_git, "unmerged", return_value=[]),
                        mock.patch.object(lean_run, "grill", return_value=("", "", False)),
                        mock.patch.object(lean_run, "run_feature", self.feature),
                        mock.patch.object(alert_email, "send", self.send)):
            patched.start()
            self.addCleanup(patched.stop)
        self.addCleanup(accounts.restrict, "")

    def feature(self, *args, **kwargs):
        self.spent.append(accounts.available())   # what the builder and any Claude reviewer may use
        return ""

    def send(self, body, flags, **kw):
        self.mails.append((kw["subject"], body))

    def run_lean(self, account=""):
        if account:
            self.profile.write_text(f"{PROFILE_BASE}\n## account\n\n    {account}\n")
        return lean.main(["--workspace", str(self.ws.root), "--repo", self.repo,
                          "--spec", str(self.spec)])

    def test_a_named_account_is_the_only_one_spent(self):
        self.run_lean("personal")
        self.assertEqual([("personal",)], self.spent)

    def test_an_account_the_machine_does_not_configure_stops_before_the_grill(self):
        with self.assertRaisesRegex(SystemExit, "GRAPH_ACCOUNTS"):
            self.run_lean("holiday")
        lean_run.grill.assert_not_called()
        self.assertEqual([], self.spent)
        self.assertIn("holiday", self.mails[0][1])

    def test_a_profile_that_makes_no_choice_is_refused_when_the_machine_has_several_accounts(self):
        with self.assertRaisesRegex(SystemExit, r"several accounts \(work, personal\).*`## account`.*`any`"):
            self.run_lean()
        lean_run.grill.assert_not_called()
        self.assertEqual("graph-loop needs the project's account", self.mails[0][0].partition("] ")[2])

    def test_any_lets_the_run_spend_every_account_in_order(self):
        self.run_lean("any")
        self.assertEqual([("work", "personal")], self.spent)

    def test_a_machine_with_one_account_has_nothing_to_choose(self):
        with mock.patch.dict(os.environ, {"GRAPH_ACCOUNTS": "work"}):
            self.run_lean()
        self.assertEqual([("work",)], self.spent)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
