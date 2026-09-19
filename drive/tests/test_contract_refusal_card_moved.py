"""A refused contract is not written over a decision made while the review ran.

The contract review is a model call of minutes, and the card it started from can
be dropped, held or rewritten in them by another writer — the decider, a drop, a
person. The refusal that comes back was decided from the older card, so writing
`refused_contract` buries whatever settled it. The rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1


def dropping(fakes: Fakes, book):
    """The reviewer answers, and another writer drops the card while it ran."""
    real = fakes.reviewer

    def reviewer(prompt, **kwargs):
        out = real(prompt, **kwargs)
        book.set_status("T1", "dropped", refused_why="decided against")
        return out

    return reviewer


class ContractRefusalCardMovedTest(unittest.TestCase):
    def test_a_card_dropped_while_the_contract_review_ran_stays_dropped(self):
        fakes = Fakes(review=[Outcome("ok", verdict="REJECT", text="1. too broad")])
        loop, book, space = loop_for(task(), fakes)
        loop.review = dropping(fakes, book)
        loop.run_task(book.task("T1"))
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
