"""Both reviewers are shown the requirement the card was granted under.

Astra's round-3 finding 8: `contract_text` showed the goal as it stands, so a
rewrite of "prove A and B" into "prove A" was judged only on A — by the contract
reviewer before the build and by the diff reviewer after it. Neither could see
that the card had been narrowed at all.

The host freezes the requirement at the FIRST contract review (and the replanner
freezes it before it narrows anything, because a card refused for its NAMES is
rewritten before any review). It is host-owned: no model writes it.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from prompts import already_read, contract_digest
from replan import replan
from test_loop import Fakes, loop_for, task
from test_replan import GOOD, answer, book_with

EXPECTED_TESTS = 6
GRANTED = {"goal": "make a.py say two and three",
           "done_when": "a.py says two and three", "sources": []}


class Reviews(Fakes):
    """The fakes, keeping what the reviewer was shown."""

    def __init__(self, **kept) -> None:
        super().__init__(**kept)
        self.seen: list[str] = []

    def reviewer(self, prompt, **kept):
        self.seen.append(prompt)
        return super().reviewer(prompt, **kept)


class FrozenRequirementTest(unittest.TestCase):
    def test_the_first_review_freezes_what_the_card_was_granted(self):
        fakes = Reviews()
        loop, book, _ = loop_for(task(source=["CLAUDE.md:5"]), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual({"goal": "make a.py say two", "done_when": "a.py says two",
                          "sources": ["CLAUDE.md:5"]},
                         book.task("T1")["requirement"])
        self.assertIn("the requirement this card was granted under", fakes.seen[0])

    def test_a_narrowed_goal_is_still_reviewed_against_the_original(self):
        fakes = Reviews()
        loop, book, _ = loop_for(task(requirement=GRANTED), fakes)
        loop.run_task(book.task("T1"))
        self.assertIn("two and three", fakes.seen[0])      # the contract review
        self.assertIn("two and three", fakes.seen[1])      # the diff review
        self.assertIn("proves less than the requirement", fakes.seen[0])
        self.assertEqual(GRANTED, book.task("T1")["requirement"])

    def test_the_replanner_freezes_it_before_it_narrows_anything(self):
        book = book_with()
        out = replan(book, book.task("T1"), lambda prompt: answer(GOOD))
        self.assertTrue(out.rewritten, out.why)
        card = book.task("T1")
        self.assertEqual("make a.py say two", card["requirement"]["goal"])
        self.assertNotEqual(card["requirement"]["goal"], card["goal"])

    def test_a_refused_rewrite_freezes_it_too(self):
        """The card whose rewrites are all refused is the decider's next, and
        the decider rewrites it before any reviewer has read it."""
        book = book_with()
        replan(book, book.task("T1"), lambda prompt: answer("I think it is fine"))
        self.assertEqual("make a.py say two", book.task("T1")["requirement"]["goal"])


class ApprovedBeforeTheFreezeTest(unittest.TestCase):
    """A card approved before the requirement existed keeps its old digest, so
    the rebuild round skipped the very review that freezes it and the card ran
    on for ever with nothing recorded (Codex, 2026-09-08)."""

    def test_a_card_with_no_requirement_goes_back_to_the_reviewer(self):
        card = task()
        approved = dict(card, contract_seen=contract_digest(card))
        self.assertFalse(already_read(approved, in_place=True, reviewed_first=False))

    def test_a_card_that_has_one_still_skips_the_second_review(self):
        card = task(requirement=GRANTED)
        approved = dict(card, contract_seen=contract_digest(card))
        self.assertTrue(already_read(approved, in_place=True, reviewed_first=False))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
