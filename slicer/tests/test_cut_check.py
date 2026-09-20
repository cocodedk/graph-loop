"""The state decides what a cut check may change; a failed ask changes nothing."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import types
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from cut_check import check
from cut_states import switch

EXPECTED_TESTS = 7


def atom(name, stage, files):
    return dict(id=name, name=name, stage=stage, goal=f"goal {name}", files=files,
                gate="g", done_when=f"done {name}")


def molecule():
    # Stages 2 and 4, not 1 and 2: a renumbering of an unchanged molecule must show.
    return dict(atoms=[atom("alpha", 2, ["a.py", "s.py"]), atom("beta", 4, ["s.py", "b.py"])])


class Scripted:
    """Answers keep_together on the cut and fail on beta's one_job; counts its calls."""

    def __init__(self, ok=True, error=None):
        self.ok, self.error, self.calls = ok, error, 0

    def __call__(self, state, questions):
        self.calls += 1
        if self.error:
            raise self.error
        answers = {}
        for question in questions:
            choice = "keep_together" if question == "cut" else "pass"
            if question == "one_job" and state["atom"]["name"] == "beta":
                choice = "fail"
            answers[question] = dict(choice=choice, confidence=0.9)
        return types.SimpleNamespace(ok=self.ok, answers=answers)


class CutCheck(unittest.TestCase):
    def setUp(self):
        self.campaign = pathlib.Path(tempfile.mkdtemp())
        self.molecule = molecule()

    def run_in(self, state, ask):
        if state != "off":
            switch(self.campaign, state, "test")
        return check(self.molecule, self.campaign, None, ask)

    def test_off_asks_nothing(self):
        ask = Scripted()
        got = self.run_in("off", ask)
        self.assertEqual(ask.calls, 0)
        self.assertIs(got.molecule, self.molecule)
        self.assertEqual((got.findings, got.verdicts), ([], []))

    def test_observe_returns_verdicts_and_changes_nothing(self):
        got = self.run_in("observe", Scripted())
        self.assertEqual(got.molecule, molecule())
        self.assertTrue(got.verdicts)
        self.assertEqual(got.findings, [])

    def test_act_merges_atoms_that_share_a_file(self):
        got = self.run_in("act", Scripted())
        self.assertEqual([a["name"] for a in got.molecule["atoms"]], ["alpha"])
        self.assertEqual(self.molecule, molecule())

    def test_act_turns_a_fail_into_a_finding(self):
        got = self.run_in("act", Scripted())
        self.assertEqual(got.findings, ["Atom beta fails the question one_job."])

    def test_not_ok_ask_changes_nothing_in_any_state(self):
        for state in ("off", "observe", "act"):
            got = self.run_in(state, Scripted(ok=False))
            self.assertEqual((got.molecule, got.findings, got.verdicts), (self.molecule, [], []))

    def test_act_with_nothing_to_merge_leaves_the_stages_alone(self):
        self.molecule["atoms"][1]["files"] = ["b.py"]
        got = self.run_in("act", Scripted())
        self.assertEqual(got.molecule, self.molecule)
        self.assertEqual([a["stage"] for a in got.molecule["atoms"]], [2, 4])

    def test_raising_ask_changes_nothing_in_any_state(self):
        for state in ("off", "observe", "act"):
            got = self.run_in(state, Scripted(error=RuntimeError("down")))
            self.assertEqual((got.molecule, got.findings, got.verdicts), (self.molecule, [], []))


if __name__ == "__main__":
    unittest.main()
