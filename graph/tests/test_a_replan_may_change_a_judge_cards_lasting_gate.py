"""A replan may change a judge card's lasting gate (issue #110).

A judge card's lasting check lives in `gate_when_kept`, so a refusal about it could not be answered by
any rewrite: the replanner said the objection targets a key its answer may not carry, and the card
parked for a person. A judge card's rewrite may now carry `gate_when_kept`, and its prompt names it.
A code card's still may not.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from replan import prompt_for, replan
from test_replan import answer, book_with

EXPECTED_TESTS = 4
JUDGE = {"gate_until_kept": True, "gate_when_kept": "run the whole class"}
REWRITE = ("goal: make a.py say two\nfiles:\n  - a.py\ngate: grep -q two a.py\ndone_when: a.py says two\n"
           "gate_when_kept: run the class with the daemon-stop trap\n")


class LastingGate(unittest.TestCase):
    def test_a_judge_cards_rewrite_may_carry_its_lasting_gate_and_it_is_stored(self):
        book = book_with(**JUDGE)
        out = replan(book, book.task("T1"), lambda prompt: answer(REWRITE))
        self.assertTrue(out.rewritten, out.why)
        self.assertEqual("run the class with the daemon-stop trap", book.task("T1")["gate_when_kept"])

    def test_a_code_cards_rewrite_may_not(self):
        book = book_with()
        out = replan(book, book.task("T1"), lambda prompt: answer(REWRITE))
        self.assertFalse(out.rewritten)
        self.assertIn("also wrote gate_when_kept", book.task("T1")["refused_why"])

    def test_only_a_judge_cards_prompt_names_the_lasting_gate(self):
        self.assertIn("gate_when_kept", prompt_for(book_with(**JUDGE).task("T1")))
        self.assertNotIn("gate_when_kept", prompt_for(book_with().task("T1")))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())   # the three above and this one


if __name__ == "__main__":
    unittest.main()
