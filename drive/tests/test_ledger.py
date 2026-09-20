"""What happened, one line each, written by code and not by me.

Three hourly reports described a stuck loop in prose and the owner could not tell
it was stuck. A ledger cannot bury the answer.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import ledger

EXPECTED_TESTS = 11


class TheLedger(unittest.TestCase):
    def test_every_ending_a_card_can_have_is_named(self):
        events = [{"at": "2026-08-31T09:12:00Z", "kind": "accepted", "task": "T25"},
                  {"at": "2026-08-31T09:13:00Z", "kind": "rejected", "task": "T26"},
                  {"at": "2026-08-31T09:14:00Z", "kind": "refused", "task": "T27"},
                  {"at": "2026-08-31T09:15:00Z", "kind": "dropped", "task": "T28"},
                  {"at": "2026-08-31T09:16:00Z", "kind": "said", "task": "T29", "state": "BLOCKED"},
                  {"at": "2026-08-31T09:17:00Z", "kind": "said", "task": "T30", "state": "PARTIAL"}]
        self.assertEqual(["KEPT", "REJECTED", "REFUSED", "DROPPED", "STOPPED", "PARTIAL"],
                         [result for _, _, result in ledger.rows(events)])

    def test_a_failed_gate_is_an_outcome(self):
        self.assertEqual([("1", "T1", "FAILED")],
                         ledger.rows([{"at": "1", "kind": "failed", "step": "gate", "task": "T1"}]))

    def test_abandoned_names_its_cards_in_a_list(self):
        """workspace_claims writes one event for the whole sweep, in `tasks`."""
        rows = ledger.rows([{"at": "1", "kind": "abandoned", "tasks": ["T1", "T2"]}])
        self.assertEqual([("1", "T1", "ABANDONED"), ("1", "T2", "ABANDONED")], rows)

    def test_a_stopped_card_is_not_printed_twice(self):
        """The builder says BLOCKED and the loop then calls for a person; that is
        one ending, not two."""
        rows = ledger.rows([{"at": "1", "kind": "said", "task": "T1", "state": "BLOCKED"},
                            {"at": "2", "kind": "needs_a_person", "task": "T1"}])
        self.assertEqual([("1", "T1", "STOPPED")], rows)

    def test_unclear_is_not_an_ending(self):
        """The builder's last line was unreadable; the loop alerts and the gate
        still judges, so the card would show UNCLEAR and then KEPT."""
        rows = ledger.rows([{"at": "1", "kind": "said", "task": "T1", "state": "UNCLEAR"},
                            {"at": "2", "kind": "accepted", "task": "T1"}])
        self.assertEqual([("2", "T1", "KEPT")], rows)

    def test_a_second_call_for_a_person_is_its_own_line(self):
        """Only the call that follows the card's own STOPPED is folded into it."""
        rows = ledger.rows([{"at": "1", "kind": "said", "task": "T1", "state": "BLOCKED"},
                            {"at": "2", "kind": "needs_a_person", "task": "T1"},
                            {"at": "3", "kind": "needs_a_person", "task": "T1"}])
        self.assertEqual([("1", "T1", "STOPPED"), ("3", "T1", "NEEDS A DECISION")], rows)

    def test_a_call_for_a_person_the_card_did_not_make_is_still_shown(self):
        rows = ledger.rows([{"at": "1", "kind": "needs_a_person", "task": "T9"}])
        self.assertEqual([("1", "T9", "NEEDS A DECISION")], rows)

    def test_bookkeeping_is_not_an_outcome(self):
        events = [{"at": "1", "kind": "claimed", "task": "T1"},
                  {"at": "2", "kind": "step", "task": "T1", "step": "build"},
                  {"at": "3", "kind": "artifact", "task": "T1"},
                  {"at": "4", "kind": "said", "task": "T1", "state": "DONE"}]
        self.assertEqual([], ledger.rows(events))

    def test_an_event_with_no_card_is_skipped(self):
        self.assertEqual([], ledger.rows([{"at": "1", "kind": "accepted"}]))

    def test_the_newest_line_is_last(self):
        events = [{"at": "2026-08-31T01:00:00Z", "kind": "accepted", "task": "T1"},
                  {"at": "2026-08-31T02:00:00Z", "kind": "accepted", "task": "T2"}]
        self.assertTrue(ledger.text(events).endswith("T2  KEPT"))
        self.assertIn("2026-08-31 01:00:00", ledger.text(events))

    def test_an_empty_log_says_so_rather_than_printing_nothing(self):
        self.assertEqual("no outcomes recorded", ledger.text([]))


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
