"""The lean loop's real call sites, with only the providers themselves faked."""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_run
import providers
import review
import tmp_root  # noqa: F401
from providers import Outcome
from test_keep import repo
from workspace import Workspace
from worktree import Worktree


class Wiring(unittest.TestCase):
    """The real call sites, with only the providers themselves faked."""

    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())
        self.tree = Worktree(repo(), "wiring").create()

    def test_the_builder_works_in_the_tree_with_the_builder_tools_and_no_push(self):
        task = {"id": "wiring", "gate": "./run-tests --all"}
        with mock.patch.object(providers, "claude", return_value=Outcome("ok", cost=0.5)) as call:
            lean_run.build(self.ws, task, "build it", self.tree)
        kw = call.call_args.kwargs
        self.assertEqual(self.tree.path, kw["cwd"])
        self.assertIn("Edit", kw["allowed_tools"])
        self.assertIn("Write", kw["allowed_tools"])
        self.assertIn("Bash(bash ", kw["allowed_tools"])
        self.assertIn("Bash(git push *)", kw["disallowed_tools"])
        paid = next(row for row in self.ws.events() if row["kind"] == "attempt")
        self.assertEqual(("wiring", "build", 0.5), (paid["task"], paid["purpose"], paid["cost"]))

    def test_the_reviewer_reads_the_tree_and_is_asked_for_the_closed_verdict(self):
        with mock.patch.object(review, "codex", return_value=Outcome("ok", verdict="ACCEPT")) as call:
            lean_run.judge(self.ws, "wiring", "the spec", "+a line", self.tree.path)
        self.assertEqual(self.tree.path, call.call_args.kwargs["cwd"])
        prompt = call.call_args.args[1]
        self.assertIn("+a line", prompt)
        self.assertIn('"review":"ACCEPT|REJECT"', prompt)
        self.assertIn("ordinary use", prompt)          # rarer edge cases are findings, not refusals
        self.assertIn("List anything rarer as a finding, and accept.", prompt)

    def test_the_suite_runs_for_real_and_a_red_one_says_why(self):
        passed, tail = lean_run.masked(self.ws, "echo the ring is grey; exit 1", self.tree.path)
        self.assertFalse(passed)
        self.assertIn("the ring is grey", tail)

    def test_every_call_logs_the_effort_it_ran_at(self):
        sent = []

        def codex(binary, prompt, *, attempt, effort, **kwargs):
            sent.append(effort)
            attempt("ok", "reviewer", 0.1, 10, "")
            return Outcome("ok", verdict="ACCEPT")
        spec = pathlib.Path(tempfile.mkdtemp()) / "a.md"
        spec.write_text("Make it blue.\n")
        with mock.patch.object(providers, "claude", return_value=Outcome("ok")) as call, \
                mock.patch.object(review, "codex", codex):
            lean_run.grill(self.ws, repo(), [str(spec)], "profile.md")
            lean_run.build(self.ws, {"id": "wiring", "gate": "true"}, "build it", self.tree)
            lean_run.judge(self.ws, "wiring", "the spec", "+a line", self.tree.path)
        paid = [(row["purpose"], row.get("effort")) for row in self.ws.events() if row["kind"] == "attempt"]
        self.assertEqual([("grill", sent[0]), ("build", call.call_args.kwargs["effort"]),
                          ("review", sent[1])], paid)   # logged is what was sent
        self.assertEqual([lean_run.REVIEW_EFFORT, providers.EFFORT, lean_run.REVIEW_EFFORT],
                         [effort for _, effort in paid])


if __name__ == "__main__":
    unittest.main()
