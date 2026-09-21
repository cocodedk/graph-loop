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
from router_probe import CATALOG, Decisions
from test_loop import Fakes, repo_with, task
from worktree import Worktree

EXPECTED_TESTS = 4


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

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
