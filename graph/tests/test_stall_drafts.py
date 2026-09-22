"""Stalls leave scrubbed Markdown evidence without asking a model."""

from __future__ import annotations

import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from driver_turn import after_lanes
from test_loop import Fakes, loop_for, task
from turn import stood_down


class StallDraftsTest(unittest.TestCase):
    def setUp(self):
        _, self.book, self.space = loop_for(task(status="rejected"), Fakes(),
                                           [task(id="T2", status="rejected")])
        self.space.event("driver_started")

    def drafts(self):
        return list((self.space.root / "issues").glob("*.md"))

    def failure(self, task_id, text="AssertionError: expected two"):
        self.space.artifact(task_id, "gate-output", text)
        self.space.attempt(task_id, account="gate", kind="ok", failed_gate=True)
        self.space.event("failed", task=task_id, step="gate", why=text[-2000:])
        self.space.event("rejected", task=task_id, why=text[-2000:])

    def test_two_cards_with_one_signature_write_one_draft_naming_both(self):
        for name in ("T1", "T2"):
            self.failure(name)
        stood_down(self.space, 78, "nothing startable")
        self.assertEqual(1, len(self.drafts()))
        body = self.drafts()[0].read_text()
        for text in ("T1", "T2", "rejected", "gate", "AssertionError", "Rule:"):
            self.assertIn(text, body)
        self.assertIn("Loop step: gate", body)

    def test_another_stall_appends_its_card_and_repeated_reads_are_idempotent(self):
        self.book.set_status("T2", "todo")
        self.failure("T1")
        stood_down(self.space, 78, "nothing startable")
        first = self.drafts()[0].read_text()
        self.book.set_status("T2", "rejected")
        self.failure("T2")
        stood_down(self.space, 78, "nothing startable")
        self.assertEqual(1, len(self.drafts()))
        both = self.drafts()[0].read_text()
        self.assertTrue(both.startswith(first))
        self.assertIn("T2", both)
        stood_down(self.space, 78, "nothing startable")
        self.assertEqual(both, self.drafts()[0].read_text())

    def test_wide_failure_window_distinguishes_a_shared_footer(self):
        footer = "runner detail\n" * 75
        self.failure("T1", "FAIL: first test\n" + footer)
        self.failure("T2", "FAIL: second test\n" + footer)
        stood_down(self.space, 78, "nothing startable")
        self.assertEqual(2, len(self.drafts()))
        self.assertTrue(all("FAIL:" in path.read_text() for path in self.drafts()))

    def test_contract_draft_reads_the_answer_beyond_the_short_event(self):
        text = "the shared introduction " * 30 + "critical refusal detail"
        self.book.set_status("T1", "refused_contract")
        self.book.set_status("T2", "done")
        self.space.artifact("T1", "contract-answer", text)
        self.space.event("refused", task="T1", step="contract", why=text[:400])
        stood_down(self.space, 78, "nothing startable")
        self.assertIn("critical refusal detail", self.drafts()[0].read_text())

    def test_every_named_person_status_and_the_boolean_hold_are_drafted(self):
        self.book.set_status("T2", "done")
        for status in ("refused_contract", "rejected", "needs_slice", "quarantined",
                       "partial_by_agent", "blocked_by_human"):
            self.book.set_status("T1", status, refused_why=status)
            self.space.event("needs_a_person", task="T1", step="build", why=status)
            stood_down(self.space, 78, "nothing startable")
        self.book.set_status("T1", "todo", blocked_by_human=True)
        self.space.event("held", task="T1", why="a human holds this card")
        stood_down(self.space, 78, "nothing startable")
        self.assertEqual(7, len(self.drafts()))

    def test_clean_stand_down_writes_no_draft_or_directory(self):
        for name in ("T1", "T2"):
            self.book.set_status(name, "done")
        stood_down(self.space, 0, "all done")
        self.assertFalse((self.space.root / "issues").exists())

    def test_watchdog_writes_the_repeated_ending_before_any_stand_down(self):
        self.book.set_status("T1", "todo")
        self.book.set_status("T2", "todo")
        for _ in range(2):
            self.failure("T1")
        args = types.SimpleNamespace(attempt_ceiling=12, hours_ceiling=2)
        with mock.patch("driver_turn.diagnose", return_value=[]):
            after_lanes(self.book, self.space, args, [self.book.task("T1")])
        self.assertEqual("quarantined", self.book.task("T1")["status"])
        self.assertEqual(1, len(self.drafts()))
        self.assertIn("same ending twice", self.drafts()[0].read_text())
        self.assertIn("AssertionError", self.drafts()[0].read_text())
        self.assertFalse(any(row["kind"] == "driver_stood_down" for row in self.space.events()))

    def test_a_later_diff_refusal_uses_its_step_and_answer_not_an_older_gate(self):
        self.book.set_status("T2", "done")
        self.failure("T1", "old gate failure")
        self.space.event("claimed", task="T1")
        self.space.event("step", task="T1", step="gate", passed=True)
        self.space.event("step", task="T1", step="diff_review", verdict="REJECT")
        self.space.artifact("T1", "diff-review-answer", "new diff finding " * 60)
        self.space.event("rejected", task="T1", why="new diff finding")
        stood_down(self.space, 78, "nothing startable")
        body = self.drafts()[0].read_text()
        self.assertIn("Loop step: diff_review", body)
        self.assertIn("new diff finding", body)
        self.assertNotIn("new diff finding " * 60, body)
        self.assertNotIn("old gate failure", body)

    def test_an_unreadable_artifact_still_drafts_the_recorded_reason(self):
        self.book.set_status("T2", "done")
        self.space.event("artifact", task="T1", name="gate-output",
                         path=str(self.space.root / "missing.txt"))
        self.space.event("failed", task="T1", step="gate", why="recorded failure")
        stood_down(self.space, 78, "nothing startable")
        self.assertIn("recorded failure", self.drafts()[0].read_text())
