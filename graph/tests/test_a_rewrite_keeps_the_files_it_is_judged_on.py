"""A card that changes code may not be rewritten into one that changes none.

Astra's round-3 finding 7: the replanner checked only that a rewrite stayed
INSIDE the card's files, so an answer of `files: []` was stored. With a narrowed
goal and a gate that passes, the card became an evidence card — no builder, no
red proof, no diff review — and the work was never done. The decider's rewrite
path already refused that (`decider_contract.check_rewrite`); the replanner was
the second caller that never asked. It asks the same validator now, so a grant
that is not a list of names is refused there too.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from replan import replan
from test_replan import answer, book_with

EXPECTED_TESTS = 3

# (what the planner answered, what it tried)
REFUSED = [
    ("goal: prove it another way\nfiles: []\ndone_when: the gate is green\n",
     "handing back a card with no files at all"),
    ("goal: prove it another way\nfiles:\ndone_when: the gate is green\n",
     "a grant that is not a list of names"),
]


# A key the planner was never asked for, carrying a value the graph check would
# read: `needs` reaches `broken_wait`, which walks it. Handed on raw, an integer
# there raised TypeError out of the whole replan — the round unspent, the card
# untouched, the same answer asked for again next turn (Codex, 2026-09-08).
# A key can also be something YAML allows and this code did not expect: `1: y`
# is the integer 1, which no message can join to a string and no sort can
# compare with one (Codex, 2026-09-08, second round).
# (what the planner answered, what it tried, what the refusal must name)
NOT_ITS_KEYS = [
    ("goal: g\nfiles: [a.py]\ndone_when: x\nneeds: 1\n", "a wait that is not a list", "needs"),
    ("goal: g\nfiles: [a.py]\ndone_when: x\nneeds: [[T1]]\n", "a wait that is not a name", "needs"),
    ("goal: g\nfiles: [a.py]\ndone_when: x\n1: y\n", "a key that is not even text", "1"),
    ("goal: g\nfiles: [a.py]\ndone_when: x\n1: y\nunknown: z\n",
     "two keys of different types", "1, unknown"),
]


class RewriteKeepsItsFilesTest(unittest.TestCase):
    def test_a_rewrite_that_writes_a_key_that_is_not_its_own_is_refused(self):
        for text, tried, named in NOT_ITS_KEYS:
            with self.subTest(tried=tried):
                book = book_with()
                out = replan(book, book.task("T1"), lambda prompt, said=text: answer(said))
                self.assertFalse(out.rewritten, out.why)
                card = book.task("T1")
                self.assertEqual(["a.py"], card["files"])
                self.assertEqual("refused_contract", card["status"])
                self.assertIn(f"also wrote {named}", card["refused_why"])
                self.assertEqual(1, card["replans"])   # the round is spent, not lost

    def test_a_rewrite_that_drops_every_file_is_refused(self):
        for text, tried in REFUSED:
            with self.subTest(tried=tried):
                book = book_with()
                out = replan(book, book.task("T1"), lambda prompt, said=text: answer(said))
                self.assertFalse(out.rewritten, out.why)
                card = book.task("T1")
                self.assertEqual(["a.py"], card["files"])
                self.assertEqual("refused_contract", card["status"])

    def test_the_round_is_spent_and_the_next_planner_reads_why(self):
        book = book_with()
        replan(book, book.task("T1"), lambda prompt: answer(REFUSED[0][0]))
        card = book.task("T1")
        self.assertEqual(1, card["replans"])
        self.assertIn("no builder is ever called for", card["refused_why"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
