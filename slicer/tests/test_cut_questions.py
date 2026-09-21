"""The questions a decisions model is asked about a molecule."""

from __future__ import annotations

import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import cut_questions

EXPECTED_TESTS = 7
CUT = {"split", "keep_together", "insufficient_evidence"}
GRADE = {"pass", "fail", "insufficient_evidence"}
ATOM_QUESTIONS = {"one_job", "claims_only_what_is_proved", "files_sufficient"}


def atom(name: str) -> dict:
    return {"name": f"atom-{name}", "goal": f"do {name}", "files": [f"{name}.py"],
            "gate": f"test {name}", "done_when": f"{name} works"}


def molecule(count: int) -> dict:
    return {"why": "a scripted one", "atoms": [atom(name) for name in "abcdef"[:count]]}


def well_formed(test: unittest.TestCase, asked_list) -> None:
    for asked in asked_list:
        test.assertTrue(asked.questions)
        for question in asked.questions.values():
            test.assertEqual("choice", question["type"])
            test.assertTrue(isinstance(question["instructions"], str)
                            and question["instructions"].strip())
            test.assertIsInstance(question["criteria"], dict)
            for text in question["criteria"].values():
                test.assertTrue(isinstance(text, str) and text.strip())


class CutTest(unittest.TestCase):
    def test_one_asked_per_adjacent_pair(self):
        whole = molecule(3)
        before = copy.deepcopy(whole)
        found = cut_questions.for_cuts(whole)
        self.assertEqual(2, len(found))
        self.assertEqual(2, len({asked.id for asked in found}))
        for asked, (one, two) in zip(found, [("a", "b"), ("b", "c")]):
            self.assertIn(f"atom-{one}", asked.id)
            self.assertIn(f"atom-{two}", asked.id)
            self.assertEqual([atom(one), atom(two)], list(asked.state.values()))
            self.assertEqual({"cut"}, set(asked.questions))
            self.assertEqual(CUT, set(asked.questions["cut"]["criteria"]))
        self.assertEqual(before, whole)
        well_formed(self, found)

    def test_a_molecule_with_no_cut_gives_nothing(self):
        self.assertEqual([], cut_questions.for_cuts(molecule(0)))
        self.assertEqual([], cut_questions.for_cuts(molecule(1)))


class AtomTest(unittest.TestCase):
    def test_one_asked_per_atom(self):
        whole = molecule(3)
        before = copy.deepcopy(whole)
        found = cut_questions.for_atoms(whole)
        self.assertEqual(3, len(found))
        self.assertEqual(3, len({asked.id for asked in found}))
        for asked, name in zip(found, "abc"):
            self.assertIn(f"atom-{name}", asked.id)
            self.assertEqual(atom(name), asked.state["atom"])
            self.assertEqual(ATOM_QUESTIONS, set(asked.questions))
            for question in asked.questions.values():
                self.assertEqual(GRADE, set(question["criteria"]))
        self.assertEqual(before, whole)
        well_formed(self, found)

    def test_a_short_molecule_does_not_raise(self):
        self.assertEqual([], cut_questions.for_atoms(molecule(0)))
        self.assertEqual(1, len(cut_questions.for_atoms(molecule(1))))

    def test_the_wall_rides_along_only_when_given(self):
        for asked in cut_questions.for_atoms(molecule(2)) \
                + cut_questions.for_atoms(molecule(2), wall=None):
            self.assertNotIn("wall", asked.state)
        for wall in ({"opaque": ["a finding"]}, {}):
            for asked in cut_questions.for_atoms(molecule(2), wall=wall):
                self.assertIn("wall", asked.state)
                self.assertIs(wall, asked.state["wall"])


class BothTest(unittest.TestCase):
    def test_no_id_repeats_across_cuts_and_atoms(self):
        whole = molecule(3)
        found = cut_questions.for_cuts(whole) + cut_questions.for_atoms(whole)
        self.assertEqual(5, len({asked.id for asked in found}))


    def test_a_colon_in_an_id_does_not_make_two_ids_the_same(self):
        whole = {"atoms": [{"name": "a"}, {"name": "b:c"}, {"name": "a:b"}, {"name": "c"}]}
        found = cut_questions.for_cuts(whole) + cut_questions.for_atoms(whole)
        self.assertEqual(7, len({asked.id for asked in found}))
        for asked, (one, two) in zip(cut_questions.for_cuts(whole),
                                     [("a", "b:c"), ("b:c", "a:b"), ("a:b", "c")]):
            self.assertIn(one, asked.id)
            self.assertIn(two, asked.id)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
