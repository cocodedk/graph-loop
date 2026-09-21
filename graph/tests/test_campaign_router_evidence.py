"""Routing asks the right question and binds effort to the actual execution."""

import importlib
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaigns import campaign
from contract import contract_digest
from router_probe import CARD, CATALOG, Decisions

EXPECTED_TESTS = 5


class RouterEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.router = importlib.import_module("model_router")
        self.catalog = patch.dict("os.environ", CATALOG)
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def choose(self, probe, space=None):
        with patch("urllib.request.urlopen", side_effect=probe):
            return self.router.choose(CARD, "build", space=space)

    def test_the_decision_question_requests_a_model_and_effort(self):
        probe = Decisions()
        self.choose(probe)
        instructions = " ".join(q["instructions"] for q in probe.requests[0]["questions"].values()).lower()
        self.assertIn("model", instructions)
        self.assertIn("effort", instructions)
        self.assertNotIn("cause explains this failed ending", instructions)

    def test_a_current_route_cannot_borrow_an_old_contracts_failed_work(self):
        _, space = campaign([CARD])
        self.route(space, "old-contract")
        self.build(space, "medium", "ok")
        space.event("failed", task=CARD["id"], step="gate", why="older failure")
        self.route(space, contract_digest(CARD))
        self.build(space, "medium", "harness")
        result = self.choose(Decisions(effort="high"), space)
        self.assertEqual(("medium", "fallback"), (result.effort, result.source))

    def test_a_medium_route_is_not_proof_that_the_actual_build_used_medium(self):
        _, space = campaign([CARD])
        self.route(space, contract_digest(CARD))
        self.build(space, "high", "ok")
        space.event("failed", task=CARD["id"], step="gate", why="high build failed")
        result = self.choose(Decisions(effort="high"), space)
        self.assertEqual(("medium", "fallback"), (result.effort, result.source))

    def test_configured_cli_aliases_do_not_bypass_family_independence(self):
        probe = Decisions(model="gpt-5.6-sol")
        with patch.dict("os.environ", {"GRAPH_BUILDERS": "sonnet,opus", "GRAPH_CLAUDE_REVIEWERS": "opus"}), \
             patch("urllib.request.urlopen", side_effect=probe):
            result = self.router.choose(CARD, "review", builder_model="sonnet")
        self.assertEqual("codex", result.resource.agent)
        for question in probe.requests[0]["questions"].values():
            for description in question["criteria"].values():
                self.assertNotIn("agent claude", description.lower())

    def route(self, space, digest):
        space.event("routed", task=CARD["id"], purpose="build", model="claude-sonnet-5",
                    agent="claude", effort="medium", source="jev", contract_digest=digest)

    def build(self, space, effort, outcome):
        space.event("step", task=CARD["id"], step="build", outcome=outcome, effort=effort,
                    on="claude:work/claude-sonnet-5")

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
