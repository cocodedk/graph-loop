"""An evidence card's gate is a long call too, and its result is not written
over a newer decision.

A card with no files never reaches a builder or a diff review: the gate runs,
and the card is written done straight after. That write was the one ending in
the loop that never asked whether the card was still the card — so a hold
raised while the gate ran was cleared and the work published under it. The rig
lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1


def after_the_review(fakes: Fakes, book, **edit):
    """A reviewer that answers, then a person writes on the card mid-round.

    The contract review is the evidence card's only model call, so this is
    where `after_the_build` would go on a card that has files.
    """
    real = fakes.reviewer

    def reviewer(prompt, **kwargs):
        out = real(prompt, **kwargs)
        book.note("T1", **edit)
        return out

    return reviewer


class EvidenceCardMovedTest(unittest.TestCase):
    def test_a_hold_raised_while_the_gate_ran_is_not_marked_done_over(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(files=[], gate="true"), fakes)
        loop.review = after_the_review(fakes, book, blocked_by_human=True)
        loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertNotEqual("done", row["status"])
        self.assertTrue(row["blocked_by_human"])
        self.assertIn("card_moved", [e["kind"] for e in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
