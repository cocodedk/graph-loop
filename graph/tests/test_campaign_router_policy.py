"""The decision router only selects offered model/effort pairs."""

import importlib
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaigns import campaign
from contract import contract_digest
from resources import Resource
from router_probe import CARD, CATALOG, Decisions

EXPECTED_TESTS = 18


class RouterPolicyTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("model_router"), "the card model router is missing")
        self.router = importlib.import_module("model_router")
        self.catalog = patch.dict("os.environ", CATALOG)
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def choose(self, probe, card=None, **kwargs):
        with patch("urllib.request.urlopen", side_effect=probe):
            return self.router.choose(card or CARD, "build", **kwargs)

    def test_a_valid_decision_selects_the_offered_model_and_effort(self):
        probe = Decisions()
        result = self.choose(probe)
        self.assertEqual(("claude-opus-5", "medium", "jev"),
                         (result.resource.model, result.effort, result.source))
        self.assertEqual(1, len(probe.requests))

    def test_unknown_choices_fall_back_to_the_configured_first_model(self):
        result = self.choose(Decisions(choice="unconfigured-model-at-max"))
        self.assertEqual(("claude-sonnet-5", "medium", "fallback"),
                         (result.resource.model, result.effort, result.source))
        self.assertTrue(result.why)

    def test_unavailable_decisions_do_not_stop_the_card(self):
        result = self.choose(Decisions(unavailable=True))
        self.assertEqual(("claude-sonnet-5", "medium", "fallback"),
                         (result.resource.model, result.effort, result.source))

    def test_low_or_nonfinite_confidence_is_not_authority(self):
        for confidence in (0.1, -0.1, 1.1, None, "0.95", float("nan"), float("inf"), True):
            with self.subTest(confidence=confidence):
                self.assertEqual("fallback", self.choose(Decisions(confidence=confidence)).source)

    def test_a_round_counter_alone_never_authorizes_higher_effort(self):
        result = self.choose(Decisions(effort="high"), {**CARD, "rebuild_round": 3})
        self.assertEqual("medium", result.effort)
        self.assertEqual("fallback", result.source)

    def test_a_recorded_failed_medium_build_can_offer_high(self):
        _, space = campaign([CARD])
        space.event("routed", task=CARD["id"], purpose="build", model="claude-sonnet-5",
                    agent="claude", effort="medium", source="jev",
                    contract_digest=contract_digest(CARD))
        space.event("step", task=CARD["id"], step="build", outcome="ok", effort="medium",
                    on="claude:work/claude-sonnet-5")
        space.event("failed", task=CARD["id"], step="gate", why="regression fails")
        result = self.choose(Decisions(effort="high"), space=space)
        self.assertEqual(("high", "jev"), (result.effort, result.source))

    def test_review_candidates_exclude_the_builders_model(self):
        probe = Decisions(model="gpt-5.6-sol")
        with patch("urllib.request.urlopen", side_effect=probe):
            result = self.router.choose(CARD, "review", builder_model="claude-sonnet-5")
        self.assertEqual("gpt-5.6-sol", result.resource.model)
        self.assertEqual("codex", result.resource.agent)
        for question in probe.requests[0]["questions"].values():
            self.assertIn("claude-opus-5", str(question["criteria"]))
            self.assertNotIn("claude-sonnet-5", str(question["criteria"]))

    def test_fallback_is_recorded_with_the_actual_choice(self):
        _, space = campaign([CARD])
        result = self.choose(Decisions(unavailable=True), space=space)
        records = [row for row in space.events() if row["kind"] == "routed"]
        self.assertTrue(records)
        record = records[-1]
        self.assertEqual((CARD["id"], "build", result.resource.model, "medium", "fallback"),
                         (record["task"], record["purpose"], record["model"], record["effort"], record["source"]))
        self.assertTrue(record.get("why"))
        self.assertEqual(result.resource.agent, record["agent"])
        self.assertEqual(contract_digest(CARD), record["contract_digest"])

    def test_offline_mode_never_contacts_the_decision_service(self):
        probe = Decisions()
        with patch.dict("os.environ", {"GRAPH_ROUTER": "off"}):
            result = self.choose(probe)
        self.assertEqual([], probe.requests)
        self.assertEqual(("medium", "fallback"), (result.effort, result.source))

    def test_review_fallback_still_excludes_the_builders_model(self):
        with patch("urllib.request.urlopen", side_effect=Decisions(unavailable=True)):
            result = self.router.choose(CARD, "review", builder_model="claude-sonnet-5")
        self.assertEqual(("codex", "gpt-6-astra", "medium", "fallback"),
                         (result.resource.agent, result.resource.model, result.effort, result.source))

    def test_no_independent_candidate_refuses_without_a_decision_call(self):
        with patch("resources.belt", return_value=[Resource("claude", "work", "claude-sonnet-5")]), \
             patch("urllib.request.urlopen") as transport, self.assertRaises(LookupError):
            self.router.choose(CARD, "review", builder_model="claude-sonnet-5")
        transport.assert_not_called()

    def test_another_contracts_medium_failure_does_not_authorize_high(self):
        self._irrelevant_failure(digest="older-contract")

    def test_an_outage_does_not_authorize_high(self):
        self._irrelevant_failure(outcome="harness")

    def test_another_cards_medium_failure_does_not_authorize_high(self):
        self._irrelevant_failure(task_id="some-other-card")

    def _irrelevant_failure(self, *, digest=None, outcome="ok", task_id=None):
        _, space = campaign([CARD])
        task_id = task_id or CARD["id"]
        space.event("routed", task=task_id, purpose="build", model="claude-sonnet-5",
                    agent="claude", effort="medium", source="jev",
                    contract_digest=digest or contract_digest(CARD))
        space.event("step", task=task_id, step="build", outcome=outcome, effort="medium",
                    on="claude:work/claude-sonnet-5")
        space.event("failed", task=task_id, step="gate", why="regression fails")
        result = self.choose(Decisions(effort="high"), space=space)
        self.assertEqual(("medium", "fallback"), (result.effort, result.source))

    def test_measured_decision_cost_is_kept_in_the_route_record(self):
        _, space = campaign([CARD])
        self.choose(Decisions(), space=space)
        record = [row for row in space.events() if row["kind"] == "routed"][-1]
        self.assertEqual(0.001, record["cost"])

    def test_single_model_skips_jev_and_records_the_first_eligible_resource(self):
        one = Resource("claude", "work", "claude-opus-5")
        other_account = Resource("claude", "personal", one.model)
        builder = Resource("codex", None, "gpt-6-astra")
        for job, belt, built_by in (("build", [one], ""), ("review", [one], ""),
                                   ("build", [one, other_account], ""),
                                   ("review", [builder, one], builder.model)):
            with self.subTest(job=job, belt=belt):
                _, space = campaign([CARD])
                with patch("resources.belt", return_value=belt), \
                     patch("model_router.ask") as ask:
                    result = self.router.choose(CARD, job, space=space, builder_model=built_by)
                ask.assert_not_called()
                self.assertEqual((one, "medium", "fallback"),
                                 (result.resource, result.effort, result.source))
                record = [row for row in space.events() if row["kind"] == "routed"][-1]
                self.assertEqual((one.model, "medium", "fallback", contract_digest(CARD)),
                                 (record["model"], record["effort"], record["source"],
                                  record["contract_digest"]))
                self.assertEqual("only one eligible model", record["why"])
                self.assertIsNone(record["cost"])

    def test_single_model_effort_uses_recorded_failure_and_respects_router_off(self):
        one = Resource("codex", None, "gpt-6-astra")
        _, space = campaign([CARD])
        space.event("routed", task=CARD["id"], purpose="build", effort="medium",
                    contract_digest=contract_digest(CARD))
        space.event("step", task=CARD["id"], step="build", outcome="ok", effort="medium")
        space.event("failed", task=CARD["id"], step="gate", why="regression fails")
        for card, job, mode, effort in ((CARD, "build", "jev", "high"),
                                       ({**CARD, "goal": "changed"}, "build", "jev", "medium"),
                                       (CARD, "review", "jev", "medium"),
                                       (CARD, "build", "off", "medium")):
            with self.subTest(job=job, mode=mode, effort=effort):
                with patch("resources.belt", return_value=[one]), \
                     patch.dict("os.environ", {"GRAPH_ROUTER": mode}), \
                     patch("model_router.ask") as ask:
                    result = self.router.choose(card, job, space=space)
                ask.assert_not_called()
                self.assertEqual(effort, result.effort)

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
