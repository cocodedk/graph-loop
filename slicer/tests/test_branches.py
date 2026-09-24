"""The branch writer writes only a closed, independently accepted branching."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "graph" / "lib"))
import cardfile  # type: ignore[import-not-found]
from branches import prompt, write_answer
from intelligence import Reply

EXPECTED_TESTS = 9

TWO = [{"name": "sign-up", "goal": "A visitor can open an account.",
        "acceptance": "A new address reaches a signed-in page."},
       {"name": "billing", "goal": "An account can pay.",
        "acceptance": "A paid account shows a receipt."}]


def answer(branches=None, result: str = "BRANCHES") -> str:
    return yaml.safe_dump({"result": result, "reason": "the brief names two capabilities",
                           "branches": TWO if branches is None else branches},
                          sort_keys=False)


class Branching(unittest.TestCase):
    def setUp(self):
        self.vault = pathlib.Path(tempfile.mkdtemp()) / "vault"

    def written(self, **kwargs):
        return write_answer(answer(**kwargs), brief="a shop", vault=self.vault,
                            reviewer=lambda question: Reply(True, "accepted"))

    def test_each_branch_is_one_numbered_note(self):
        state, paths = self.written()
        self.assertEqual("written", state)
        self.assertEqual(["01-sign-up.md", "02-billing.md"],
                         [path.name for path in paths])      # type: ignore[union-attr]

    def test_a_branch_note_carries_its_goal_and_what_would_be_observed(self):
        _, paths = self.written()
        note = cardfile.load(paths[0])                       # type: ignore[index]
        self.assertEqual("A visitor can open an account.", note["goal"])
        self.assertEqual("A new address reaches a signed-in page.", note["why"])
        self.assertEqual("branch", note["status"])

    def test_an_independent_rejection_writes_nothing(self):
        state, why = write_answer(answer(), brief="a shop", vault=self.vault,
                                  reviewer=lambda question: Reply(False, why="not observable"))
        self.assertEqual(("review_refused", "not observable"), (state, why))
        self.assertFalse(self.vault.exists())

    def test_a_branch_missing_its_acceptance_is_refused(self):
        with self.assertRaisesRegex(ValueError, "name, goal and acceptance"):
            self.written(branches=[{"name": "sign-up", "goal": "open an account"}])

    def test_an_empty_acceptance_is_refused(self):
        with self.assertRaisesRegex(ValueError, "acceptance must say something"):
            self.written(branches=[{"name": "a", "goal": "g", "acceptance": "  "}])

    def test_a_branching_that_writes_one_note_writes_them_all_or_none(self):
        # The FIRST note of this branching is already there and the second is
        # new; neither may land, or the next run plans half a graph.
        self.written()
        with self.assertRaises(FileExistsError):
            write_answer(answer([TWO[0], {"name": "shipping", "goal": "g",
                                          "acceptance": "a parcel leaves"}]),
                         brief="a shop", vault=self.vault,
                         reviewer=lambda question: Reply(True))
        self.assertEqual(["01-sign-up.md", "02-billing.md"],
                         sorted(p.name for p in self.vault.iterdir()))

    def test_needs_person_is_a_closed_non_write(self):
        text = yaml.safe_dump({"result": "NEEDS_PERSON", "reason": "the brief says nothing",
                               "branches": None})
        state, why = write_answer(text, brief="", vault=self.vault)
        self.assertEqual(("needs_person", "the brief says nothing"), (state, why))
        self.assertFalse(self.vault.exists())

    def test_the_prompt_states_the_one_rule_for_where_a_branch_ends(self):
        self.assertIn("observed with every other branch absent", prompt("a shop", self.vault))

    def test_the_reviewer_is_asked_to_apply_that_rule_branch_by_branch(self):
        """It was one refusal in a list of five, and the reviewer skimmed past
        it: six branches for "link in, text out" were ACCEPTED, and the spec
        reviewer rejected the same thing one level down, twice, for naming no
        observable consequence (2026-09-18). The rule was right and was being
        applied a layer too late."""
        asked = []

        def judge(question):
            asked.append(" ".join(question.split()))
            return Reply(False, why="read")

        write_answer(answer(), brief="a shop", vault=self.vault, reviewer=judge)
        self.assertIn("ONE AT A TIME", asked[0])
        self.assertIn("with every other branch deleted", asked[0])
        # the exact shape that slipped through: a step nobody can see on its own
        self.assertIn("only consequence is that a later branch can run", asked[0])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
