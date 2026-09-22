"""Prepared path choices use the existing client, confidence gate and finite belt."""

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import resources
import tmp_root  # noqa: F401
from providers import Outcome
from triage_path_jev import OPTIONS, choose
from workspace import Workspace


class PathQuestionTest(unittest.TestCase):
    def setUp(self):
        self.space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="cards")
        self.task = {"id": "T1"}
        self.space.event("released", task="T1")

    def decide(self, out, stall="judge_gap"):
        with mock.patch("triage_jev.ask", return_value=out) as ask:
            row = choose(self.space, self.task, stall, {"refusal": "judge misses a case"})
        return row, ask

    def test_every_prepared_option_is_recorded_with_confidence_and_spend(self):
        for stall, options in OPTIONS.items():
            for path in options:
                with self.subTest(stall=stall, path=path):
                    self.space.event("released", task="T1")
                    row, ask = self.decide(Outcome("ok", verdict=path, confidence=.9,
                                                   cost=.01, tokens=20), stall)
                    self.assertEqual((path, .9), (row["path"], row["confidence"]))
                    body = json.loads(ask.call_args.args[0])
                    self.assertEqual(set(options) | {"unknown"},
                                     set(body["questions"]["cause__0"]["criteria"]))
                    attempts = [r for r in self.space.events() if r["kind"] == "attempt"]
                    self.assertEqual((.01, 20, "triage"),
                                     tuple(attempts[-1][k] for k in ("cost", "tokens", "purpose")))

    def test_low_missing_invalid_confidence_and_unknown_need_a_person_without_fallback(self):
        for confidence in (None, False, .5, .1, -1, 2, float("nan"), float("inf"), .9):
            with self.subTest(confidence=confidence):
                self.space.event("released", task="T1")
                verdict = "unknown" if confidence == .9 else "probe_in_gate"
                with mock.patch("triage_path_jev.text_call") as fallback:
                    row, _ = self.decide(Outcome("ok", verdict=verdict, confidence=confidence))
                self.assertEqual("needs_person", row["path"])
                fallback.assert_not_called()

    def test_unavailable_jev_uses_the_existing_finite_text_belt(self):
        belt = [resources.Resource("claude", "one", "opus"),
                resources.Resource("claude", "one", "sonnet"),
                resources.Resource("claude", "two", "opus")]
        answers = [Outcome("limit"), Outcome("ok", text=json.dumps({
            "verdict": "probe_in_gate", "why": "a named case"}))]
        with mock.patch("resources.belt", return_value=belt), \
                mock.patch("triage_intelligence._call", side_effect=answers) as fallback:
            row, ask = self.decide(Outcome("capacity", text="unavailable"))
        self.assertEqual("probe_in_gate", row["path"])
        self.assertEqual((1, 2), (ask.call_count, fallback.call_count))
        self.assertIn("accept_with_observation", fallback.call_args.args[0])

    def test_exhausted_or_malformed_fallback_needs_a_person(self):
        for out in (Outcome("capacity"), Outcome("ok", text="not JSON"),
                    Outcome("ok", text='{"verdict":"work","why":"wrong question"}')):
            self.space.event("released", task="T1")
            with mock.patch("triage_path_jev.text_call", return_value=out):
                row, _ = self.decide(Outcome("harness"))
            self.assertEqual("needs_person", row["path"])

    def test_replay_reads_the_record_without_another_call(self):
        row, _ = self.decide(Outcome("ok", verdict="probe_in_gate", confidence=.9))
        again, ask = self.decide(Outcome("ok", verdict="needs_person", confidence=.9))
        self.assertEqual(row, again)
        ask.assert_not_called()

    def test_marker_precedes_the_call_and_an_interruption_never_calls_again(self):
        with mock.patch("triage_jev.ask", side_effect=RuntimeError("process died")), \
                self.assertRaises(RuntimeError):
            choose(self.space, self.task, "judge_gap", {})
        row, ask = self.decide(Outcome("ok", verdict="probe_in_gate", confidence=.9))
        self.assertEqual("needs_person", row["path"])
        ask.assert_not_called()

    def test_an_ending_cannot_ask_a_second_stall_question(self):
        self.decide(Outcome("ok", verdict="probe_in_gate", confidence=.9))
        row, ask = self.decide(Outcome("ok", verdict="accept_change", confidence=.9),
                               "fixed_criteria")
        self.assertEqual("needs_person", row["path"])
        ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
