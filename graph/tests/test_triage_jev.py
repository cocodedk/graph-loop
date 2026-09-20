"""The Jev rung: one cause, or nothing at all and the text belt decides."""

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / "lib"), str(HERE / "tests")]
import provider_jev
import resources
import tmp_root  # noqa: F401 — every temp file of this process under one root
import triage_jev
from providers import Outcome
from test_triage_intelligence import ending  # the same ending, written once
from triage_evidence import Ending
from triage_intelligence import LABEL, decide_unknown
from triage_signatures import VERDICTS
from workspace import Workspace

EXPECTED_TESTS = 14
BELT = [resources.Resource("claude", "work", "opus")]
TEXT_ANSWER = Outcome("ok", text='{"verdict":"gate","why":"mute check"}')


def said(choice: str) -> Outcome:
    return provider_jev._read(json.dumps({"answers": {"cause": {
        "type": "choice", "choice": choice, "confidence": 0.9}}}), triage_jev.DECIDING)


class TableTest(unittest.TestCase):
    def test_the_causes_are_the_verdicts_triage_already_knows(self):
        self.assertEqual(sorted(VERDICTS), sorted(triage_jev.CAUSES))

    def test_unknown_is_asked_but_never_acted_on(self):
        self.assertIn("unknown", triage_jev.CAUSES)
        self.assertEqual(sorted(set(VERDICTS) - {"unknown"}),
                         sorted(triage_jev.DECIDING))


class EvidenceTest(unittest.TestCase):
    """Jev is handed the facts, not the record. Measured: the record halves it."""

    def setUp(self):
        self.long = Ending(
            "T9", {"id": "T9", "status": "out_of_scope", "files": ["src/a.java"]},
            ({"kind": "build", "step": "builder", "why": "wrote the test"},
             {"kind": "failed", "step": "file_fence", "why": "wrote outside its files"}),
            {"build-log": ("x" * 5000,)}, ("x" * 5000,))

    def test_only_the_step_that_stopped_it_is_handed_over(self):
        facts = triage_jev.evidence(self.long)
        self.assertEqual("file_fence", facts["the_step_that_stopped_it"])
        self.assertEqual("wrote outside its files", facts["what_it_said"])
        self.assertNotIn("wrote the test", json.dumps(facts))

    def test_the_notes_are_bounded_and_the_events_are_not_there(self):
        facts = triage_jev.evidence(self.long)
        self.assertEqual(triage_jev.NOTES, len(facts["notes"]))
        self.assertNotIn("events", facts)
        self.assertFalse(facts["the_card_s_check_was_run"])


class RealEndingTest(unittest.TestCase):
    """Campaign 7's own two failed endings, in its `events.jsonl` order.

    Every ending the loop closes ends in `released`, which carries no step and
    no message, so reading the last event handed Jev the two fields the question
    turns on empty. No test caught it: the endings written here all ended on
    their failure. `rebuild_queued` names no step, which is the other half.
    """

    def ending(self, *events) -> Ending:
        return Ending("execute-post-fetch", {"id": "execute-post-fetch",
                                             "status": "rejected", "files": []},
                      events, {}, ())

    def test_the_contract_refusal_is_read_and_not_the_release(self):
        facts = triage_jev.evidence(self.ending(
            {"kind": "claimed"}, {"kind": "step", "step": "contract"},
            {"kind": "refused", "step": "contract",
             "why": "the done-when never asserts the User-Agent the goal requires"},
            {"kind": "released"}))

        self.assertEqual("contract", facts["the_step_that_stopped_it"])
        self.assertIn("never asserts the User-Agent", facts["what_it_said"])

    def test_a_rebuild_takes_the_step_the_lane_was_last_in(self):
        facts = triage_jev.evidence(self.ending(
            {"kind": "step", "step": "gate"}, {"kind": "step", "step": "diff_review"},
            {"kind": "rebuild_queued", "round": 1,
             "why": "the connection is left with the default redirect following"},
            {"kind": "released"}))

        self.assertEqual("diff_review", facts["the_step_that_stopped_it"])
        self.assertIn("default redirect following", facts["what_it_said"])

    def test_an_alert_on_a_healthy_ending_stopped_nothing(self):
        facts = triage_jev.evidence(self.ending(
            {"kind": "step", "step": "push"},
            {"kind": "alert", "why": "kept as 41617809 but not pushed"},
            {"kind": "accepted"}, {"kind": "released"}))

        self.assertEqual("", facts["the_step_that_stopped_it"])
        self.assertEqual("", facts["what_it_said"])


class RungTest(unittest.TestCase):
    def setUp(self):
        self.space = Workspace(pathlib.Path(tempfile.mkdtemp()) / "campaign")
        self.key = mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "k"})
        self.key.start()
        self.addCleanup(self.key.stop)

    def decide(self, answer, belt=BELT):
        with mock.patch.object(resources, "belt", return_value=belt) as asked, \
                mock.patch.object(triage_jev, "ask", return_value=answer), \
                mock.patch("triage_intelligence._call", return_value=TEXT_ANSWER):
            return decide_unknown(ending(), self.space), asked

    def records(self, kind: str) -> list[dict]:
        return [row for row in self.space.events()
                if row["kind"] == kind and row.get("task") == LABEL]

    def test_one_named_cause_is_the_verdict_and_the_belt_is_never_asked(self):
        decision, belt = self.decide(said("work"))
        self.assertEqual(("work", "jev"), (decision.verdict, decision.signature))
        belt.assert_not_called()
        self.assertEqual(["plan"], [row["account"] for row in self.records("attempt")])
        self.assertEqual(["jev-question", "jev-answer"],
                         [row["name"] for row in self.records("artifact")])

    def test_an_unreadable_answer_leaves_the_belt_to_decide(self):
        decision, _belt = self.decide(Outcome("harness", text="nope"))
        self.assertEqual(("gate", "model"), (decision.verdict, decision.signature))

    def test_an_unknown_answer_leaves_the_belt_to_decide(self):
        decision, _belt = self.decide(said("unknown"))
        self.assertEqual(("gate", "model"), (decision.verdict, decision.signature))

    def test_an_option_off_the_list_is_not_a_verdict(self):
        decision, _belt = self.decide(Outcome("ok", verdict="beats me"))
        self.assertEqual(("gate", "model"), (decision.verdict, decision.signature))

    def test_the_prompt_nobody_was_sent_is_not_recorded(self):
        self.decide(said("work"))
        self.assertEqual([], [row for row in self.records("artifact")
                              if row["name"] == "triage-prompt"])

    def test_the_rung_is_asked_whether_or_not_we_hold_the_key(self):
        """A gateway can attach the key we cannot see, so only the answer decides."""
        with mock.patch.dict("os.environ", {}, clear=True):
            decision, _belt = self.decide(said("work"))
        self.assertEqual(("work", "jev"), (decision.verdict, decision.signature))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
