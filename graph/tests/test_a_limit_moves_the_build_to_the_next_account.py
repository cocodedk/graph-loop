"""A builder call that hits an account's limit moves to the next account (issue #253).

`lean_run.build` always used `accounts.available()[0]`, so the run stopped on the first account's spend
limit though GRAPH_ACCOUNTS configured a second one. A limit now moves the call on, and logs it; a project
whose profile names its account has only that one, so it stops there as before.
"""

import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import accounts
import lean_run
import provider_words
import tmp_root  # noqa: F401
from providers import Outcome
from workspace import Workspace

EXPECTED_TESTS = 4
SPEND = "You've hit your individual spend limit"


class Fall(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())
        self.tree = types.SimpleNamespace(path=tempfile.mkdtemp())
        self.task = {"id": "rest-ring", "gate": "true", "budget": 8}
        self.used = []

    def build(self, answers, names=("work", "second")):
        def claude(binary, prompt, *, account, resume="", **_kw):
            self.used.append((account, resume))
            return answers[account]
        with mock.patch.object(lean_run.providers, "claude", claude), \
                mock.patch.object(accounts, "available", return_value=names):
            return lean_run.build(self.ws, self.task, "prompt", self.tree, resume="s1")

    def test_a_limit_moves_the_call_to_the_next_account_without_the_first_ones_session(self):
        out = self.build({"work": Outcome("limit", text=SPEND), "second": Outcome("ok", text="built")})
        self.assertEqual("ok", out.kind)
        self.assertEqual([("work", "s1"), ("second", "")], self.used)
        (event,) = [row for row in self.ws.events() if row["kind"] == "lean_account_limit"]
        self.assertEqual(("rest-ring", "work"), (event["task"], event["account"]))

    def test_every_account_at_its_limit_ends_as_a_limit(self):
        out = self.build({"work": Outcome("limit"), "second": Outcome("limit")})
        self.assertEqual(("limit", ["work", "second"]), (out.kind, [name for name, _ in self.used]))

    def test_a_project_that_names_its_account_never_leaves_it(self):
        out = self.build({"work": Outcome("limit")}, names=("work",))
        self.assertEqual(("limit", ["work"]), (out.kind, [name for name, _ in self.used]))

    def test_the_issues_own_message_is_read_as_a_limit(self):
        self.assertEqual("limit", provider_words._classify_text(SPEND))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the four above and this one


if __name__ == "__main__":
    unittest.main()
