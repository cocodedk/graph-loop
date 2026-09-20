"""A contract edited after its acceptance is one nobody has read."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from prompts import already_read, contract_digest

EXPECTED_TESTS = 3

# Every accepted card carries the requirement its first review froze, so a
# fixture without one is a card the loop can no longer produce: `already_read`
# sends it back to the reviewer rather than skipping the freeze (Codex,
# 2026-09-08). The fixture moved; what these three assert did not.
CARD = {"id": "T1", "goal": "do the thing", "files": ["app.py"], "gate": "false",
        "done_when": "the test passes",
        "requirement": {"goal": "do the thing", "done_when": "the test passes",
                        "sources": []}}


class AlreadyReadTest(unittest.TestCase):
    def test_a_rebuild_round_skips_the_review_for_the_contract_it_accepted(self):
        card = dict(CARD, contract_seen=contract_digest(CARD))
        self.assertTrue(already_read(card, in_place=True, reviewed_first=False))

    def test_an_edited_contract_goes_back_to_the_review(self):
        card = dict(CARD, contract_seen=contract_digest(CARD))
        edited = dict(card, gate="false\n(cd x && grep -q y z) || exit 1")
        self.assertFalse(already_read(edited, in_place=True, reviewed_first=False))

    def test_a_card_that_never_recorded_one_is_never_already_read(self):
        self.assertFalse(already_read(dict(CARD), in_place=True, reviewed_first=True))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
