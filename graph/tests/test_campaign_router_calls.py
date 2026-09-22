"""The real build and review paths use the decision, not an unused router."""

import json
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))
import graph_commands
from loop import Loop
from loop_steps import build
from providers import Outcome
from resources import Resource
from router_probe import CATALOG, Decisions
from test_loop import Fakes, repo_with, task
from worktree import Worktree

EXPECTED_TESTS = 7


class RouterCallsTest(unittest.TestCase):
    def build_one(self, probe):
        fakes, calls = Fakes(), []
        root, book, space = repo_with(task())
        tree = Worktree(root, "T1").create()
        self.addCleanup(tree.remove)

        def builder(prompt, **kwargs):
            calls.append(kwargs)
            return fakes.builder(prompt, **kwargs)

        loop = Loop(repo=root, backlog=book, space=space, build=builder, review=fakes.reviewer)
        with patch.dict("os.environ", CATALOG), patch("urllib.request.urlopen", side_effect=probe):
            out = build(loop, book.task("T1"), tree)
        self.assertIsNone(out)
        return calls, space

    def test_the_build_call_uses_the_chosen_model_at_medium(self):
        calls, space = self.build_one(Decisions())
        self.assertEqual(("claude-opus-5", "medium"), (calls[0]["model"], calls[0]["effort"]))
        self.assertTrue(any(row["kind"] == "routed" for row in space.events()))

    def test_the_build_call_falls_back_without_raising_effort(self):
        calls, _ = self.build_one(Decisions(unavailable=True))
        self.assertEqual(("claude-sonnet-5", "medium"), (calls[0]["model"], calls[0]["effort"]))

    def test_the_independent_review_call_uses_its_own_route(self):
        root, _, space = repo_with(task(builder_model="claude-sonnet-5", builder_agent="claude"))
        probe = Decisions(model="gpt-5.6-sol")
        response = subprocess.CompletedProcess([], 0, json.dumps(
            {"review": "ACCEPT", "accept": True, "findings": []}), "")
        with patch.dict("os.environ", CATALOG), patch("urllib.request.urlopen", side_effect=probe), \
             patch("provider_codex._run", return_value=response) as call:
            result = graph_commands._real_review("Review this card", cwd=root, space=space, task_id="T1")
        self.assertTrue(result.ok)
        argv = call.call_args.args[0]
        self.assertEqual("gpt-5.6-sol", argv[argv.index("--model") + 1])
        self.assertIn('model_reasoning_effort="medium"', argv)

    def test_no_independent_reviewer_produces_no_accepted_review(self):
        for metadata in ({"builder_model": "claude-sonnet-5", "builder_agent": "claude"}, {}):
            with self.subTest(metadata=metadata):
                root, _, space = repo_with(task(**metadata))
                with patch.dict("os.environ", CATALOG), \
                     patch("resources.belt", return_value=[Resource("claude", "work", "claude-sonnet-5")]), \
                     patch("provider_codex._run") as codex_call, \
                     patch("providers.claude", return_value=Outcome(
                         "ok", text="REVIEW: ACCEPT")) as claude_call:
                    result = graph_commands._real_review("Review this card", cwd=root, space=space, task_id="T1")
                self.assertFalse(result.ok)
                self.assertNotEqual("ACCEPT", result.verdict)
                codex_call.assert_not_called()
                claude_call.assert_not_called()

    def test_codex_exhaustion_falls_back_to_a_different_claude_model(self):
        root, _, space = repo_with(task(builder_model="claude-sonnet-5", builder_agent="claude"))
        with patch.dict("os.environ", CATALOG), \
             patch("urllib.request.urlopen", side_effect=Decisions(model="gpt-5.6-sol")), \
             patch("review._one_review", return_value=Outcome("capacity")) as codex_call, \
             patch("review._claude_review", return_value=Outcome(
                 "ok", verdict="ACCEPT", text="REVIEW: ACCEPT")) as claude_call:
            result = graph_commands._real_review("Review this card", cwd=root, space=space, task_id="T1")
        self.assertEqual("ACCEPT", result.verdict)
        self.assertEqual(2, codex_call.call_count)
        self.assertEqual(["claude-opus-5"],
                         [call.args[1].model for call in claude_call.call_args_list])

    def test_review_fallback_records_each_actual_model_and_effort(self):
        root, _, space = repo_with(task(builder_model="claude-sonnet-5", builder_agent="claude"))
        answers = [Outcome("capacity"), Outcome("ok", verdict="ACCEPT", text="fine")]
        with patch.dict("os.environ", CATALOG), \
             patch("urllib.request.urlopen", side_effect=Decisions(model="gpt-5.6-sol")), \
             patch("review._one_review", side_effect=answers):
            result = graph_commands._real_review("Review this card", cwd=root, space=space, task_id="T1")
        self.assertEqual("ACCEPT", result.verdict)
        actual = [(row["model"], row["effort"]) for row in space.events()
                  if row["kind"] != "routed" and row.get("purpose") == "review" and row.get("model")]
        self.assertEqual([("gpt-5.6-sol", "medium"), ("gpt-6-astra", "medium")], actual)

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
