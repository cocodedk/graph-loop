"""The contract the reviewer reads is the whole card, so its digest binds it.

Astra's review of 2026-09-08, section D: `contract_text` showed the goal, the
files, the gate, the done-when and the note, and left out what the card waits
for, the names it uses and creates, the phrase its red proof must print, and
the card it was cut from. So a card whose waits or red proof were edited after
its acceptance still carried a matching `contract_seen`, and the round built a
contract nobody had read.

Codex on that fix: pasting the values into one text made the boundaries
guessable, so a note ending in a line that reads like the wait list produced
the same text — and the same digest — as a card that really waits for T0. Each
value is JSON now, so a newline inside one is not a new field.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from prompts import already_read, contract_digest, contract_prompt

EXPECTED_TESTS = 9

# The requirement is on the card because every accepted card carries one: without
# it `already_read` refuses on that ground alone, and the two edit tests below
# would pass even if the digest stopped reading `needs` or `expect_red` at all
# (Codex, 2026-09-08).
CARD = {"id": "T1", "goal": "do the thing", "files": ["app.py"], "gate": "false",
        "done_when": "the test passes", "needs": ["T0"], "uses": ["seen_at"],
        "creates": ["risk_score"], "expect_red": "has no attribute 'risk_score'",
        "sliced_from": "T9",
        "requirement": {"goal": "do the thing", "done_when": "the test passes",
                        "sources": []}}


def edited_after_acceptance(**edits: object) -> dict:
    """The card the reviewer accepted, changed afterwards."""
    return dict(CARD, contract_seen=contract_digest(CARD), **edits)


class ContractFieldsTest(unittest.TestCase):
    def test_a_kept_judges_coverage_is_not_the_code_cards_review(self):
        sentence = ("If this card's judge is already kept, judge this card's own files and gate, "
                    "not the judge's coverage, and do not require bypass probes or refuse "
                    "this card for gaps in that judge.\n")
        self.assertIn(sentence, contract_prompt(CARD))
        self.assertNotIn(sentence, contract_prompt(dict(CARD, gate_until_kept=True)))

    def test_review_targets_real_bypasses_and_blocking_files(self):
        prompt = contract_prompt(CARD)
        for rule in ("Can this gate pass without the work being done, and do the files cover what the gate can fail on?",
                     "Name a concrete bypass or a blocking file", "Assume an honest builder",
                     "hard-coding the judge's expected values", "a lookup table keyed on test data",
                     "the diff review's finding, not grounds to refuse a contract",
                     "Incidental implementation description in Goal/Done-when/Note",
                     "need not be mechanically asserted by the gate"):
            self.assertIn(rule, prompt)

    def test_only_a_test_delivery_may_edit_the_test_its_gate_runs(self):
        self.assertIn("Refuse it if the builder can edit the test its gate runs", contract_prompt(CARD))
        delivery = contract_prompt(dict(CARD, gate_files_are_the_work=True))
        self.assertIn("that is the deliverable", delivery)
        self.assertIn("Do not refuse it for being able to edit that file", delivery)

    def test_a_new_wait_is_a_contract_nobody_has_read(self):
        card = edited_after_acceptance(needs=["T0", "T5"])
        self.assertFalse(already_read(card, in_place=True, reviewed_first=False))

    def test_the_contract_it_accepted_is_still_the_one_it_accepted(self):
        """The other side of the two below: an untouched approved card skips the
        review, so a test that goes red there is reading the digest, not a card
        that was going back to the reviewer whatever the digest said."""
        self.assertTrue(already_read(edited_after_acceptance(),
                                     in_place=True, reviewed_first=False))

    def test_an_edited_red_proof_is_a_contract_nobody_has_read(self):
        card = edited_after_acceptance(expect_red="AssertionError: 2 != 1")
        self.assertFalse(already_read(card, in_place=True, reviewed_first=False))

    def test_a_note_cannot_be_written_to_look_like_the_wait_list(self):
        # The note below ends in the line a `needs` of ["T0"] used to print.
        # Both cards then read as one text, so a card given a real dependency
        # mid-round kept its acceptance and was published over.
        pretending = dict(CARD, needs=[], note='n\nwaits for: [\'T0\']')
        waiting = dict(CARD, needs=["T0"], note="n")
        self.assertNotEqual(contract_digest(pretending), contract_digest(waiting))

    def test_the_reviewer_is_shown_every_field_the_digest_binds(self):
        prompt = contract_prompt(CARD)
        for line in ('waits for: ["T0"]',
                     'uses: ["seen_at"]',
                     'creates: ["risk_score"]',
                     'red proof must contain: "has no attribute \'risk_score\'"',
                     'sliced from: "T9"'):
            self.assertIn(line, prompt)

    def test_a_path_reads_as_itself_and_a_newline_still_does_not(self):
        # Non-ASCII characters stay readable; quotes, backslashes and control
        # characters are still escaped, and the newline is the one that makes
        # the boundary. Escaping the accent too made a file the reviewer must
        # recognise unreadable for nothing.
        prompt = contract_prompt(dict(CARD, files=["café.py"], gate="false\nsecond leg"))
        self.assertIn('files: ["café.py"]', prompt)
        self.assertIn('gate: "false\\nsecond leg"', prompt)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
