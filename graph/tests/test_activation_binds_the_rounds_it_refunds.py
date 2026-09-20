"""A repair sends the card back to its builder, and that is approved too.

The approval recorded the gate each card would get and nothing about the status
and the rounds the same write hands back — so a card whose spent rounds changed
after the approval was repaired anyway, and refunded a different number from the
one the decider was shown (astra's round-4 finding 11: "including status/refund
changes"). Every field the repair reads is part of what the approval says it
will find. The rig is `test_two_repairs_on_one_card.previewing`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_two_repairs_on_one_card import GATE, previewing
from triage_routes import activate_preview

EXPECTED_TESTS = 1


class ApprovedRefundTest(unittest.TestCase):
    def test_a_card_whose_spent_rounds_changed_is_not_repaired_on_the_old_approval(self):
        book, space = previewing("mute-gate")
        # One of the rounds it spent turns out not to be the gate's, so the
        # refund the approval showed is not the refund this card would get.
        book.note("T1", gate_rounds=2)

        activate_preview(book, space, space.events())

        card = book.task("T1")
        self.assertEqual(GATE, card["gate"])                  # not repaired
        self.assertEqual("rejected", card["status"])          # and not sent back
        self.assertEqual([], [one for one in space.events()
                              if one.get("kind") == "triage_activation"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
