"""The ending keeps every card still owed, whole, as it keeps every drop.

`gaps` is the sentence a reader is shown and it is cut at 400 characters, so
three cards and their reasons left the receipt as one and a half — and `left`
kept the ids alone, without the status each stopped in or why. What the
campaign never proved is the record, not the sentence about it (Codex on
33b9c76b, finding 2). The drops learned this first (an independent review, finding 2).
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import source_gap
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from campaigns import campaign
from finishing import ENDED_WITH_GAPS, stand_down

EXPECTED_TESTS = 1
WHY = ("the diff does not prove the replay: the journal is read back in the same "
       "process that wrote it, so nothing says the broker survived a restart, and "
       "the gate greps a line the test itself prints")
CARDS = [{"id": f"T{number}", "status": "rejected", "goal": "prove the broker replays",
          "files": [f"b{number}.py"], "gate": "true", "needs": [],
          "refused_why": f"{WHY} ({number})"} for number in (1, 2, 3)]


class EveryCardOwedTest(unittest.TestCase):
    def test_three_cards_of_reasons_survive_the_sentence_that_cuts_them(self):
        book, space = campaign([dict(one) for one in CARDS])

        self.assertEqual(ENDED_WITH_GAPS, stand_down(space, book))
        gaps = source_gap.ended(space)
        assert gaps is not None
        self.assertEqual(["T1", "T2", "T3"], [one["id"] for one in gaps["unfinished"]])
        for card, kept in zip(CARDS, gaps["unfinished"], strict=True):
            self.assertIn(card["refused_why"], kept["why"])
            self.assertIn("rejected", kept["why"])
        self.assertLess(400, len(gaps["gaps"]) + 1)   # more than the sentence can hold


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
