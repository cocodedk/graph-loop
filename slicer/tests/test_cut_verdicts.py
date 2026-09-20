"""A verdict below the gate changes nothing; a confident one merges or names an atom."""

from __future__ import annotations

import pathlib
import sys
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from cut_questions import _cut_id
from cut_verdicts import apply_merges, findings, merges, read

EXPECTED_TESTS = 10


def atom(name, stage, files, gate="g"):
    return dict(name=name, stage=stage, goal=f"goal {name}", files=files,
                gate=gate, done_when=f"done {name}")


MOLECULE = dict(atoms=[atom("alpha", 1, ["a.py", "s.py"], "gate one"),
                       atom("beta", 2, ["s.py", "b.py"], "gate two"),
                       atom("gamma", 3, ["c.py"])])


def asked(ident, *questions):
    return types.SimpleNamespace(id=ident, questions={q: {} for q in questions})


def answer(ok=True, **given):
    rows = {q: dict(choice=c, confidence=p) for q, (c, p) in given.items()}
    return types.SimpleNamespace(ok=ok, answers=rows)


def cut(choice, confidence, ident=_cut_id("alpha", "beta")):
    return read(asked(ident, "cut"), answer(cut=(choice, confidence)))


class CutVerdicts(unittest.TestCase):
    def test_a_verdict_below_the_gate_is_not_usable_and_does_nothing(self):
        low = cut("keep_together", 0.59) + read(asked("atom:alpha", "one_job"), answer(one_job=("fail", 0.3)))
        self.assertFalse(any(v.usable for v in low))
        self.assertEqual(merges(MOLECULE, low), [])
        self.assertEqual(findings(MOLECULE, low), [])

    def test_a_confidence_that_is_not_a_number_is_not_usable(self):
        for bad in (None, "0.9", True):
            self.assertFalse(cut("keep_together", bad)[0].usable)

    def test_a_usable_keep_together_merges_adjacent_atoms_that_share_a_file(self):
        self.assertEqual(merges(MOLECULE, cut("keep_together", 0.6)), [("alpha", "beta")])

    def test_atoms_that_share_no_file_are_not_merged(self):
        self.assertEqual(merges(MOLECULE, cut("keep_together", 0.9, _cut_id("beta", "gamma"))), [])

    def test_atoms_that_are_not_adjacent_are_not_merged(self):
        self.assertEqual(merges(MOLECULE, cut("keep_together", 0.9, _cut_id("alpha", "gamma"))), [])

    def test_a_split_or_another_question_does_not_merge(self):
        self.assertEqual(merges(MOLECULE, cut("split", 0.9)), [])
        other = read(asked(_cut_id("alpha", "beta"), "one_job"), answer(one_job=("keep_together", 0.9)))
        self.assertEqual(merges(MOLECULE, other), [])

    def test_a_usable_fail_names_the_atom_and_the_question(self):
        got = read(asked("atom:beta", "one_job"), answer(one_job=("fail", 0.8)))
        self.assertEqual(len(findings(MOLECULE, got)), 1)
        text = findings(MOLECULE, got)[0]
        self.assertIn("beta", text)
        self.assertIn("one_job", text)

    def test_apply_merges_unites_files_keeps_gates_in_order_and_renumbers(self):
        made = apply_merges(MOLECULE, [("alpha", "beta")])
        first, last = made["atoms"]
        self.assertEqual(first["files"], ["a.py", "b.py", "s.py"])
        self.assertEqual(first["gate"], "gate one\ngate two")
        self.assertEqual(first["goal"], "goal alpha\ngoal beta")
        self.assertEqual(first["done_when"], "done alpha\ndone beta")
        self.assertEqual([first["stage"], last["stage"]], [1, 2])
        self.assertEqual(last["name"], "gamma")
        self.assertEqual(len(MOLECULE["atoms"]), 3)

    def test_overlapping_pairs_lose_nothing_whatever_order_they_come_in(self):
        four = dict(atoms=[atom(n, i, ["s.py"], f"gate {n}") for i, n in enumerate(("alpha", "beta", "gamma", "delta"), 1)])
        made = apply_merges(four, [("beta", "gamma"), ("alpha", "beta"), ("gamma", "delta")])
        (only,) = made["atoms"]
        self.assertEqual(only["name"], "alpha")
        self.assertEqual(only["stage"], 1)
        self.assertEqual(only["gate"], "gate alpha\ngate beta\ngate gamma\ngate delta")
        self.assertEqual(only["goal"], "goal alpha\ngoal beta\ngoal gamma\ngoal delta")
        self.assertEqual(only["done_when"], "done alpha\ndone beta\ndone gamma\ndone delta")

    def test_an_answer_that_is_not_ok_gives_no_verdicts_and_nothing_raises(self):
        self.assertEqual(read(asked(_cut_id("alpha", "beta"), "cut"), answer(ok=False, cut=("keep_together", 1))), [])
        self.assertEqual(read(object(), object()), [])
        self.assertEqual(merges(None, []), [])
        self.assertEqual(findings({}, []), [])
        self.assertIsNone(apply_merges(None, [("a", "b")]))
        self.assertEqual(apply_merges(MOLECULE, [("x", "y")])["atoms"][0]["name"], "alpha")


if __name__ == "__main__":
    unittest.main()
