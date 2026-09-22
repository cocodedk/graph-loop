"""The driver's commands, unit-tested where they decide something: which
refused contracts the top-of-turn replan may touch."""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE))

import graph_commands
import real_calls
from backlog import Backlog
from graph_commands import replan_pending
from providers import Outcome
from workspace import Workspace

EXPECTED_TESTS = 9


def book(**changes) -> Backlog:
    row = {"id": "T1", "goal": "g", "status": "refused_contract", "files": [], "gate": "true",
           "done_when": "x", "refused_why": "too broad"}
    row.update(changes)
    path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
    path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": [row]}, sort_keys=False))
    return Backlog(path)


class ReplanPendingTest(unittest.TestCase):
    def test_a_refused_contract_with_rounds_left_is_rewritten(self):
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        calls = []
        answer = yaml.safe_dump({"goal": "g2", "files": [], "gate": "true", "done_when": "y"})
        replan_pending(book(), space, lambda prompt, account: calls.append(prompt) or Outcome("ok", text=answer))
        self.assertEqual(1, len(calls))

    def test_a_live_contract_is_left_to_the_commander_who_wrote_it(self):
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        calls = []
        replan_pending(book(gate_has_side_effects=True), space, lambda prompt, account: calls.append(prompt) or Outcome("ok", text=""))
        self.assertEqual([], calls)

    def test_a_held_contract_is_left_to_the_person_who_holds_it(self):
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        calls = []
        replan_pending(book(blocked_by_human=True), space, lambda prompt, account: calls.append(prompt) or Outcome("ok", text=""))
        self.assertEqual([], calls)


class RecordedCallsTest(unittest.TestCase):
    def test_every_planner_call_leaves_its_own_record(self):
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        answers = ["not: a contract", yaml.safe_dump({"goal": "g2", "files": [], "gate": "true", "done_when": "y"})]
        replan_pending(book(gate="true"), space, lambda prompt, account: Outcome("ok", text=answers.pop(0), cost=1.5))
        calls = [row for row in space.events() if row.get("step") == "replan_call"]
        self.assertEqual(2, len(calls))                    # both, not a summary of the last
        self.assertEqual([1.5, 1.5], [row.get("cost") for row in calls])
        prompts = [row for row in space.events() if row.get("name") == "replan-prompt"]
        self.assertEqual(2, len(prompts))


class PlannerCallTest(unittest.TestCase):
    def test_the_planner_reads_the_campaign_checkout_with_its_own_timeout(self):
        import turn
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            space = Workspace(root / "campaign").init(
                goal="g", backlog="b.yaml", repo=str(repo))
            answer = yaml.safe_dump({"goal": "g2", "files": [],
                                     "gate": "true", "done_when": "y"})
            with unittest.mock.patch.object(turn, "claude", return_value=Outcome("ok", text=answer)) as call:
                replan_pending(book(), space)
            call.assert_called_once()
            seen = call.call_args.kwargs
        self.assertTrue(seen.get("read_only"))
        self.assertFalse(seen.get("no_tools", False))
        self.assertEqual(str(repo), seen.get("cwd"))
        self.assertEqual(900, seen.get("timeout"))


class RealReviewCwdTest(unittest.TestCase):
    """_real_review must judge the worktree it is given, never the driver's
    own checkout (independent review, Codex GPT-5.6, 2026-09-02)."""

    def test_the_codex_call_changes_into_the_given_worktree_read_only(self):
        import review
        seen = {}

        def fake_run(argv, stdin, env, timeout):
            seen["argv"] = argv
            return unittest.mock.Mock(   # returncode: a verdict needs a call that finished
                returncode=0,
                stdout='{"review": "ACCEPT", "accept": true, "findings": []}', stderr="")

        belt = [review.resources.Resource("codex", None, "m1")]
        # the call itself lives in `provider_codex` now; the review only reads it
        with unittest.mock.patch.object(review.resources, "belt", return_value=belt), \
             unittest.mock.patch("real_calls._routed_task", return_value={"builder_model": "builder"}), \
             unittest.mock.patch("provider_codex._run", side_effect=fake_run):
            out = graph_commands._real_review("judge this", cwd="/worktrees/T1", effort="high")
        self.assertEqual("ACCEPT", out.verdict)
        self.assertEqual("/worktrees/T1", seen["argv"][seen["argv"].index("--cd") + 1])
        self.assertNotIn("workspace-write", seen["argv"])   # a reviewer never writes what it grades

    def test_the_claude_call_receives_the_given_worktree_as_cwd(self):
        import review
        seen = {}

        def fake_claude(binary, prompt, **kwargs):
            seen.update(kwargs)
            return Outcome("ok", text="REVIEW: ACCEPT")

        belt = [review.resources.Resource("claude", "work", "claude-opus-5")]
        with unittest.mock.patch.object(review.resources, "belt", return_value=belt), \
             unittest.mock.patch("providers.claude", fake_claude):
            out = review.codex("codex", "judge this", cwd="/worktrees/T1", effort="medium")
        self.assertEqual("ACCEPT", out.verdict)
        self.assertEqual("/worktrees/T1", seen.get("cwd"))


class RealReviewLedgerTest(unittest.TestCase):
    """Every paid review call reaches the campaign ledger, the same way a
    build's does (lib/loop_steps.py `loop.space.attempt(...)` per belt call)
    — `_real_review` binds codex's own `attempt` callback to the task it is
    reviewing, when the caller gives it a workspace and a task id."""

    def test_a_review_leaves_one_ledger_row_under_its_account_and_task(self):
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog=str(book(status="todo").path))

        def fake_codex(binary, prompt, *, cwd="", effort="", attempt=None, **_settings):
            if attempt:
                attempt("ok", "second", 0.4, 900, "fine")
            return Outcome("ok", verdict="ACCEPT", text="fine")

        with unittest.mock.patch.object(real_calls, "codex", fake_codex):
            graph_commands._real_review("judge this", cwd="/worktrees/T1", effort="high",
                                        space=space, task_id="T1")
        rows = [row for row in space.events() if row.get("kind") == "attempt"]
        self.assertEqual([("T1", "second", 0.4, 900, "review")],
                         [(row["task"], row["account"], row["cost"], row["tokens"], row.get("purpose"))
                          for row in rows])


class TimestampedOutputTest(unittest.TestCase):
    def test_every_report_line_has_a_utc_timestamp_and_is_flushed(self):
        output = io.StringIO()
        stamp = "2026-09-22T12:34:56Z"
        with contextlib.redirect_stdout(output), \
             unittest.mock.patch.object(output, "flush") as flushed, \
             unittest.mock.patch.object(graph_commands, "_now", return_value=stamp), \
             unittest.mock.patch.object(graph_commands, "_space"), \
             unittest.mock.patch.object(graph_commands, "report"), \
             unittest.mock.patch.object(graph_commands, "as_text", return_value="first\n\nlast\n"):
            self.assertEqual(0, graph_commands.command_report(None))
        self.assertEqual([f"{stamp} first", f"{stamp} ", f"{stamp} last", f"{stamp} "],
                         output.getvalue().splitlines())
        flushed.assert_called_once()


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
