"""The lean loop's real call sites, with only the providers themselves faked."""

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_run
import models
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

    def test_the_builder_runs_on_the_blocks_model(self):
        body = json.dumps({"result": "done", "session_id": "s1", "total_cost_usd": 0.1,
                           "usage": {"input_tokens": 1, "output_tokens": 1}, "permission_denials": []})
        done = subprocess.CompletedProcess([], 0, body, "")
        with mock.patch.object(providers, "_run", return_value=done) as run:
            lean_run.build(self.ws, {"id": "wiring", "gate": "./run-tests --all"}, "build it", self.tree)
        argv = run.call_args.args[0]
        self.assertEqual(models.LEAN["builder"]["model"], argv[argv.index("--model") + 1])

    def test_a_repair_build_sends_and_logs_its_own_effort(self):
        with mock.patch.object(providers, "claude", return_value=Outcome("ok")) as call:
            lean_run.build(self.ws, {"id": "wiring", "gate": "true"}, "fix it", self.tree,
                           resume="s1", effort=models.LEAN["repair"]["effort"])
        self.assertEqual((models.LEAN["repair"]["effort"], "s1"), (call.call_args.kwargs["effort"], call.call_args.kwargs["resume"]))
        paid = next(row for row in self.ws.events() if row["kind"] == "attempt")
        self.assertEqual(models.LEAN["repair"]["effort"], paid["effort"])

    def test_the_reviewer_reads_the_tree_and_is_asked_for_the_closed_verdict(self):
        with mock.patch.object(review, "codex", return_value=Outcome("ok", verdict="ACCEPT")) as call:
            lean_run.judge(self.ws, "wiring", "the spec", "+a line", self.tree.path)
        self.assertEqual(self.tree.path, call.call_args.kwargs["cwd"])
        prompt = call.call_args.args[1]
        self.assertIn("+a line", prompt)
        self.assertIn('"review":"ACCEPT|REJECT"', prompt)
        self.assertIn("any defect you can name", prompt)   # a named defect is refused; notes are for small things
        self.assertIn("Accept, listing findings, only for style, a stated limit or a suggestion", prompt)
        self.assertIn("ACCEPT requires accept=true and may list findings that block nothing", prompt)
        self.assertNotIn("no findings", prompt)   # one answer rule, never one that overrides another

    def test_the_suite_runs_for_real_and_a_red_one_says_why(self):
        passed, tail = lean_run.masked(self.ws, "echo the ring is grey; exit 1", self.tree.path)
        self.assertFalse(passed)
        self.assertIn("the ring is grey", tail)
        gate = next(row for row in self.ws.events() if row["kind"] == "lean_gate")
        self.assertEqual(("ran", 1), (gate["ended"], gate["code"]))
        self.assertIn("confined", gate)

    def test_a_gate_that_never_finished_says_so_first(self):
        with mock.patch.object(lean_run.gates, "run_gate", return_value=lean_run.gates.GateResult(
                124, "partial output", kind="timeout")):
            passed, tail = lean_run.masked(self.ws, "sleep 9", self.tree.path)
        self.assertFalse(passed)
        self.assertTrue(tail.startswith("The command did not run to the end (timeout).\n"), tail)

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
        self.assertEqual([models.LEAN["review"]["effort"], models.LEAN["builder"]["effort"], models.LEAN["review"]["effort"]],
                         [effort for _, effort in paid])


if __name__ == "__main__":
    unittest.main()
