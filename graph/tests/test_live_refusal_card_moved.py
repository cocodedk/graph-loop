"""A live card decided while its round ran keeps that decision.

A live round that ends in anything but done or blocked is parked
`live_turn_ended`, so the next turn cannot repeat a live action on a moved
stack. But a round that ended `held` ended because ANOTHER writer decided the
card while the round ran — the guard every ending passes — and parking it there
writes over the very decision that guard preserved: a dropped card came back
held for a person. The rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1
LIVE = {"gate_has_side_effects": True, "helper_verbs": ["journal"], "gate": "true",
        "files": [], "triage": "unknown"}


def dropping(fakes: Fakes, book):
    """The reviewer answers, and another writer drops the card while it ran."""
    real = fakes.reviewer

    def reviewer(prompt, **kwargs):
        out = real(prompt, **kwargs)
        book.set_status("T1", "dropped", refused_why="decided against")
        return out

    return reviewer


class LiveRefusalCardMovedTest(unittest.TestCase):
    def test_a_live_card_dropped_while_its_contract_was_read_stays_dropped(self):
        fakes = Fakes(review=[Outcome("ok", verdict="REJECT", text="1. too broad")])
        loop, book, space = loop_for(task(**LIVE), fakes)
        loop.review = dropping(fakes, book)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("held", out.state)
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
