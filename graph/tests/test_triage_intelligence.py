"""The conveyor belt gets one bounded chance at an unknown ending."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import resources
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import Outcome
from triage_evidence import Ending
from triage_intelligence import LABEL, _call, decide_unknown
from workspace import Workspace

EXPECTED_TESTS = 6


def ending() -> Ending:
    return Ending("T1", {"id": "T1", "status": "needs_slice", "files": ["a.py"]},
                  ({"kind": "failed", "step": "gate", "why": "one assert"},),
                  {"gate-output": ("AssertionError",)}, ("AssertionError",))


class IntelligenceTest(unittest.TestCase):
    def test_blocked_footer_parks_before_triage_can_route_it(self):
        from distress import INSTRUCTION, TEMPLATE
        from test_distress import BLOCKED, DONE
        from test_replan import book_with
        from triage import triage_pending
        from triage_intelligence import _read
        for footer in (BLOCKED, DONE.replace('false, "why": ""',
                       'true, "why": "missing inputs"')):
            book = book_with(status="todo")
            space = Workspace(tempfile.mkdtemp())
            space.event("triage_preview")
            space.event("claimed", task="T1")
            space.artifact("T1", "gate-output", "one assertion failed")
            space.event("failed", task="T1", step="gate")
            space.event("released", task="T1")
            call = mock.Mock(return_value=Outcome("ok", text=
                '{"verdict":"contract","why":"rewrite it"}\n' + footer))
            with mock.patch.object(resources, "belt", return_value=[
                    resources.Resource("claude", "work", "opus")]):
                triage_pending(book, space, call=call)
                triage_pending(book, space, call=call)
            self.assertEqual("blocked_by_agent", book.task("T1")["status"])
            self.assertFalse(book.startable())
            self.assertEqual(book.task("T1")["refused_why"], next(e["why"] for e in space.events()
                                              if e["kind"] == "needs_a_person"))
            call.assert_called_once()
            self.assertIn(INSTRUCTION + TEMPLATE, call.call_args.args[0])
            self.assertFalse(any(e["kind"] == "triage_proposal" for e in space.events()))
        self.assertEqual("work", _read('{"verdict":"work","why":"fix"}\n' + DONE).verdict)


    def setUp(self):
        self.space = Workspace(pathlib.Path(tempfile.mkdtemp()) / "campaign")

    @mock.patch.object(resources, "belt", return_value=[
        resources.Resource("claude", "work", "opus")])
    def test_one_closed_answer_becomes_the_decision(self, _belt):
        seen = []
        said = decide_unknown(
            ending(), self.space,
            lambda prompt, resource: seen.append((prompt, resource)) or Outcome(
                "ok", text='{"verdict":"work","why":"one concern"}'))
        self.assertEqual(("work", "model"), (said.verdict, said.signature))
        self.assertEqual(1, len(seen))
        attempts = [e for e in self.space.events()
                    if e["kind"] == "attempt" and e["task"] == LABEL]
        self.assertEqual(1, len(attempts))
        self.assertEqual("triage", attempts[0].get("purpose"))

    @mock.patch.object(resources, "belt", return_value=[
        resources.Resource("claude", "work", "opus")])
    def test_an_open_or_extra_shape_stays_unknown(self, _belt):
        for answer in ('{"verdict":"work"}',
                       '{"verdict":"work","verdict":"gate","why":"x"}',
                       '{"verdict":"work","why":"x","command":"run me"}',
                       '```json\n{"verdict":"work","why":"x"}\n```'):
            with self.subTest(answer=answer):
                said = decide_unknown(ending(), self.space,
                                      lambda _p, _r, value=answer: Outcome("ok", text=value))
                self.assertEqual("unknown", said.verdict)

    @mock.patch.object(resources, "belt", return_value=[
        resources.Resource("claude", "work", "opus"),
        resources.Resource("claude", "personal", "opus")])
    def test_a_resource_refusal_walks_the_belt(self, _belt):
        calls = []
        def ask(_prompt, resource):
            calls.append(resource.account)
            return (Outcome("limit", cost=0, tokens=0) if len(calls) == 1 else
                    Outcome("ok", text='{"verdict":"rig","why":"fixture"}'))
        said = decide_unknown(ending(), self.space, ask)
        self.assertEqual(("work", "personal"), tuple(calls))
        self.assertEqual("rig", said.verdict)

    @mock.patch("triage_intelligence.claude", return_value=Outcome("ok"))
    def test_the_real_call_has_no_tools_and_medium_effort(self, called):
        _call("prompt", resources.Resource("claude", "work", "opus"))
        self.assertTrue(called.call_args.kwargs["no_tools"])
        self.assertEqual("medium", called.call_args.kwargs["effort"])
        self.assertEqual("opus", called.call_args.kwargs["model"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
