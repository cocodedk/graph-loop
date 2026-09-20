"""A card that has spent its rebuild rounds is never offered again.

The cap was read only where a review rejected a diff. A card left `todo` by any
other path — a review that never happened, a replan — kept its round count and
the picker handed it back, so a fourth and fifth round were paid for.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog import Backlog
from backlog_status import REBUILD_ROUNDS
from doctor_starved import check_starved

EXPECTED_TESTS = 5


def backlog_of(*rows) -> Backlog:
    path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"tasks": list(rows)}), "utf-8")
    return Backlog(path)


def card(**extra) -> dict:
    row = {"id": "T1", "goal": "g", "status": "todo", "needs": []}
    row.update(extra)
    return row


class ThePickerReadsTheCap(unittest.TestCase):
    def test_a_card_at_the_cap_is_not_offered(self):
        book = backlog_of(card(rebuild_round=REBUILD_ROUNDS))
        self.assertEqual([], book.ready())

    def test_a_card_one_round_short_still_is(self):
        book = backlog_of(card(rebuild_round=REBUILD_ROUNDS - 1))
        self.assertEqual(["T1"], [row["id"] for row in book.ready()])

    def test_a_card_that_never_rebuilt_still_is(self):
        self.assertEqual(["T1"], [row["id"] for row in backlog_of(card()).ready()])


class TheDoctorSaysItOutLoud(unittest.TestCase):
    def test_a_card_the_picker_will_not_offer_is_named(self):
        found = check_starved([card(rebuild_round=REBUILD_ROUNDS)], claimed=0)
        self.assertEqual(1, len(found))
        self.assertIn("T1", found[0].what)

    def test_a_queue_with_real_work_and_no_spent_cards_says_nothing(self):
        self.assertEqual([], check_starved([card()], claimed=0))


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
