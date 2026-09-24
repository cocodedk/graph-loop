"""The ending's receipt holds every dropped card, whole.

What the campaign did not prove is the only record of it: the display line is
cut at 400 characters, and joining every drop into that one line lost the cards
past it — id, reason and all (an independent review, finding 2). The receipt keeps
them as a list nothing truncates; only the sentence a reader is shown is cut.
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

EXPECTED_TESTS = 2
WHY = "no approved source names the broker journal, and none of the cards around it says so either"
MANY = 6      # six of those reasons is well past the 400-character display cut


def gone(number: int) -> dict:
    return {"id": f"T{number}", "status": "dropped", "goal": f"prove part {number}",
            "files": [f"b{number}.py"], "gate": "true", "needs": [],
            "refused_why": f"{WHY} ({number})"}


class EveryDropTest(unittest.TestCase):
    def setUp(self) -> None:
        self.book, self.space = campaign([gone(n) for n in range(MANY)])
        self.assertEqual(ENDED_WITH_GAPS, stand_down(self.space, self.book))
        self.receipt = source_gap.ended(self.space)
        assert self.receipt is not None

    def test_every_dropped_card_is_in_the_receipt_with_its_whole_reason(self):
        self.assertGreater(len("; ".join(f"{one['id']}: {one['why']}"
                                         for one in self.receipt["dropped"])), 400)
        self.assertEqual([f"T{n}" for n in range(MANY)],
                         [one["id"] for one in self.receipt["dropped"]])
        for number, one in enumerate(self.receipt["dropped"]):
            self.assertEqual(f"{WHY} ({number})", one["why"])

    def test_only_the_line_a_reader_is_shown_is_cut(self):
        self.assertLessEqual(len(self.receipt["gaps"]), 400)
        self.assertIn("T0", self.receipt["gaps"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
