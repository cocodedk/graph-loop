"""One block in `lib/models.py` names every lean model and effort; a lean call reads it when it is made.

The calls are faked (`test_lean_run.Rig`, a fake `providers.claude`, a fake codex transport); no model runs."""

import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_run
import models
import providers
import resources
import review
import tmp_root  # noqa: F401
from providers import Outcome
from test_lean_run import Rig

EXPECTED_TESTS = 7
REAL_BUILD = lean_run.build
CHANGED = {"builder": {"model": "b-model", "effort": "b-effort"}, "repair": {"model": "r-model", "effort": "r-effort"},
           "grill": {"model": "g-model", "effort": "g-effort"}, "review": {"model": "v-model", "effort": "v-effort"}}


class TheBlock(unittest.TestCase):
    def test_it_holds_the_four_calls_and_jev(self):
        self.assertEqual({"builder": {"model": "claude-sonnet-5-5", "effort": "high"},
                          "repair": {"model": "claude-sonnet-5-5", "effort": "medium"},
                          "grill": {"model": "gpt-6.1-sol", "effort": "medium"},
                          "review": {"model": "gpt-6.1-sol", "effort": "medium"},
                          "jev": {"model": "typesafe/jev-1.13", "probability": 0.8, "confidence": 0.75}},
                         models.LEAN)

    def test_the_codex_reviewers_start_with_the_review_model(self):
        with mock.patch.dict(os.environ, {"GRAPH_REVIEWERS": ""}):
            self.assertEqual((models.LEAN["review"]["model"],), models.reviewers())
            with mock.patch.dict(models.LEAN, CHANGED):
                self.assertEqual(("v-model",), models.reviewers())

    def test_the_providers_and_lean_run_take_their_values_from_it(self):
        self.assertEqual((models.LEAN["builder"]["model"], models.LEAN["review"]["model"],
                          models.LEAN["review"]["effort"]),
                         (providers.MODEL, providers.REVIEW_MODEL, providers.REVIEW_EFFORT))
        self.assertEqual((models.LEAN["builder"]["effort"], models.LEAN["repair"]["effort"]),
                         (lean_run.BUILD_EFFORT, lean_run.REPAIR_EFFORT))

    def test_graph_reviewers_replaces_the_list_and_never_appends(self):
        with mock.patch.dict(os.environ, {"GRAPH_REVIEWERS": "first, second"}):
            self.assertEqual(("first", "second"), models.reviewers())
            for job in ("review", "grill"):
                self.assertEqual(["first", "second"],
                                 [item.model for item in resources.belt(job) if item.agent == "codex"])


class TheCallsFollowIt(Rig):
    def events(self):
        return [(row["purpose"], row["model"], row["effort"]) for row in self.ws.events()
                if row["kind"] == "lean_call_started"]

    def test_the_build_and_the_repair_are_called_with_the_blocks_values(self):
        calls = []

        def claude(_binary, _prompt, **kwargs):
            calls.append((kwargs["model"], kwargs["effort"]))
            (pathlib.Path(kwargs["cwd"]) / "ring.py").write_text(f"amber {len(calls)}\n")
            return Outcome("ok", session="s1", cost=0.1)

        def build(ws, task, prompt, tree, resume="", effort=""):
            return REAL_BUILD(ws, task, prompt, tree, resume, effort)
        with mock.patch.object(providers, "claude", claude), mock.patch.dict(models.LEAN, CHANGED):
            self.run_it(build, suites=(False, True))
        self.assertEqual([("b-model", "b-effort"), ("r-model", "r-effort")], calls)
        self.assertEqual([("build", "b-model", "b-effort"), ("build", "r-model", "r-effort"),
                          ("review", "v-model", "v-effort")], self.events())

    def transport(self, calls):
        def codex_text(_binary, _prompt, *, model, effort, **_kwargs):
            calls.append((model, effort))
            return Outcome("ok", text="REVIEW: ACCEPT")
        return mock.patch.object(review, "codex_text", codex_text)

    def test_the_review_is_called_with_the_blocks_values(self):
        calls = []
        with self.transport(calls), mock.patch.dict(models.LEAN, CHANGED), mock.patch.dict(os.environ, {"GRAPH_REVIEWERS": ""}):
            out = lean_run.judge(self.ws, "feature", "spec", "diff", "/tmp")
        self.assertEqual(("ACCEPT", [("v-model", "v-effort")]), (out.verdict, calls))
        self.assertEqual([("review", "v-model", "v-effort")], self.events())

    def test_the_grill_is_called_with_the_blocks_values(self):
        calls = []
        with self.transport(calls), mock.patch.dict(models.LEAN, CHANGED), mock.patch.dict(os.environ, {"GRAPH_REVIEWERS": ""}):
            lean_run.grill(self.ws, self.repo, [str(self.spec)], "profile.md")
        self.assertEqual([("g-model", "g-effort")], calls)
        self.assertEqual([("grill", "g-model", "g-effort")], self.events())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
