"""Replanning stops for repetition or six rounds, never for new findings alone."""

import tempfile
import unittest
from unittest.mock import Mock

import tmp_root  # noqa: F401 — keep temporary test repositories under the suite's root
from backlog_decision import can_replan
from backlog_status import is_wall
from replan import replan, replan_until_planned
from replan_budget import MAX_ROUNDS, alert_stopped, same_complaint, stop_reason
from slice_outcome import MAX_SLICES
from test_replan import GOOD, answer, book_with
from turn import replan_pending
from workspace import Workspace

REASONS = ("The gate accepts a comment instead of executing the implementation.",
           "An absent output file is silently ignored by the shell pipeline.",
           "The fixture hardcodes every input and cannot detect a constant return.")


class ReplanBudgetTest(unittest.TestCase):
    def test_three_different_refusals_do_not_exhaust_two_round_budget(self):
        book = book_with(triage="contract")
        for reason in REASONS:
            book.set_status("T1", "refused_contract", refused_why=reason)
            row = book.task("T1")
            self.assertTrue(can_replan(row))
            self.assertFalse(is_wall(row))
            self.assertTrue(replan(book, row, lambda prompt: answer(GOOD)).rewritten)
        self.assertEqual(3, book.task("T1")["replans"])
        self.assertEqual(list(REASONS), book.task("T1")["replan_history"])

    def test_same_refusal_twice_stops_before_paying_for_another_replan(self):
        book = book_with(refused_why=REASONS[0], triage="contract")
        replan(book, book.task("T1"), lambda prompt: answer(GOOD))
        book.set_status("T1", "refused_contract", refused_why=REASONS[0].upper())
        row = book.task("T1")
        planner = Mock()
        self.assertFalse(can_replan(row))
        self.assertTrue(is_wall(row))
        self.assertIn("the same complaint twice", replan(book, row, planner).why)
        planner.assert_not_called()

    def test_comparison_is_normalised_text_with_a_fixed_similarity_threshold(self):
        self.assertTrue(same_complaint("Missing   OUTPUT\nfile.", "missing output file."))
        self.assertTrue(same_complaint(REASONS[0], REASONS[0].replace("a comment", "comments")))
        self.assertFalse(same_complaint(REASONS[0], REASONS[1]))
        self.assertFalse(same_complaint("", ""))

    def test_only_the_previous_refusal_counts_and_other_cards_are_independent(self):
        book = book_with(replans=2, replan_history=list(REASONS[:2]), refused_why=REASONS[0])
        self.assertTrue(can_replan(book.task("T1")))
        other = book_with(id="T2", refused_why=REASONS[1])
        self.assertTrue(can_replan(other.task("T2")))

    def test_quoted_material_never_changes_the_complaint(self):
        book = book_with(refused_why=REASONS[0] + "\n\n```kotlin\nreturn 0\n```")
        replan(book, book.task("T1"), lambda prompt: answer(GOOD))
        self.assertEqual([REASONS[0]], book.task("T1")["replan_history"])
        book.set_status("T1", "refused_contract",
                        refused_why=REASONS[0] + "\n\n> unrelated contract prompt")
        self.assertEqual("the same complaint twice", stop_reason(book.task("T1")))

    def test_varying_refusals_stop_at_six_and_need_a_slice(self):
        book = book_with()
        space = Workspace(tempfile.mkdtemp()).init(goal="test", backlog=str(book.path))
        planner = Mock(side_effect=lambda prompt, resource: answer(GOOD))
        for number in range(MAX_ROUNDS):
            book.set_status("T1", "refused_contract", refused_why=REASONS[number % 3])
            self.assertTrue(replan_pending(book, space, planner))
        book.set_status("T1", "refused_contract", refused_why=REASONS[0])
        self.assertFalse(replan_pending(book, space, planner))
        self.assertEqual(MAX_ROUNDS, planner.call_count)
        self.assertEqual(MAX_ROUNDS, book.task("T1")["replans"])
        self.assertEqual("needs_slice", book.task("T1")["status"])
        self.assertFalse(space.alerts(unread_only=False))

    def test_repetition_needs_a_slice_without_alerting_a_person(self):
        book = book_with(replans=1, replan_history=[REASONS[0]], refused_why=REASONS[0],
                         triage="contract", slices=MAX_SLICES - 1)
        space = Workspace(tempfile.mkdtemp()).init(goal="test", backlog=str(book.path))
        planner = Mock()
        self.assertFalse(replan_until_planned(book, book.task("T1"), planner, space=space).rewritten)
        self.assertFalse(replan_pending(book, space, planner))
        planner.assert_not_called()
        row = book.task("T1")
        self.assertEqual("needs_slice", row["status"])
        self.assertTrue(is_wall(row))
        self.assertEqual(MAX_SLICES - 1, row["slices"])
        self.assertEqual([REASONS[0]], row["replan_history"])
        self.assertEqual(REASONS[0], row["refused_why"])
        self.assertFalse(space.alerts(unread_only=False))

    def test_rejected_rewrites_need_a_slice_without_a_workspace(self):
        book = book_with(triage="contract")
        planner = Mock(return_value=answer("not a contract"))
        self.assertFalse(replan_until_planned(book, book.task("T1"), planner).rewritten)
        self.assertEqual(2, planner.call_count)
        self.assertEqual("needs_slice", book.task("T1")["status"])
        self.assertTrue(is_wall(book.task("T1")))

    def test_slice_ceiling_still_holds_for_a_person_and_alerts_once(self):
        book = book_with(replans=MAX_ROUNDS, slices=MAX_SLICES, triage="contract")
        space = Workspace(tempfile.mkdtemp()).init(goal="test", backlog=str(book.path))
        planner = Mock()
        for _ in range(2):
            self.assertFalse(replan_pending(book, space, planner))
        planner.assert_not_called()
        row = book.task("T1")
        self.assertEqual("refused_contract", row["status"])
        self.assertTrue(row["blocked_by_human"])
        self.assertEqual("loop", row["held_by"])
        self.assertEqual(MAX_SLICES, row["slices"])
        self.assertFalse(is_wall(row))
        self.assertEqual(1, len(space.alerts(unread_only=False)))
        self.assertIn("the ceiling", space.alerts(unread_only=False)[0])

    def test_live_cards_and_human_holds_keep_their_behavior(self):
        for fields in ({"gate_has_side_effects": True},
                       {"blocked_by_human": True, "held_by": "person"}):
            with self.subTest(fields=fields):
                book = book_with(replans=MAX_ROUNDS, **fields)
                before = book.task("T1")
                space = Workspace(tempfile.mkdtemp()).init(goal="test", backlog=str(book.path))
                self.assertFalse(replan_pending(book, space, Mock()))
                self.assertEqual(before, book.task("T1"))
                self.assertEqual(1, len(space.alerts(unread_only=False)))

    def test_stop_handler_reads_the_current_card(self):
        book = book_with(replans=MAX_ROUNDS)
        stale = book.task("T1")
        book.set_status("T1", "done")
        alert_stopped(book, None, stale)
        self.assertEqual("done", book.task("T1")["status"])

    def test_needs_slice_keeps_the_other_eligibility_guards(self):
        for verdict in ("work", "contract", "harness", None):
            with self.subTest(verdict=verdict):
                row = {"status": "needs_slice", "triage": verdict, "files": ["a.py"]}
                self.assertEqual(verdict in ("work", "contract"), is_wall(row))
                self.assertFalse(is_wall({**row, "blocked_by_human": True}))
                self.assertFalse(is_wall({**row, "gate_has_side_effects": True}))
                if verdict == "contract":
                    for status in ("out_of_scope", "quarantined", "rejected"):
                        self.assertFalse(is_wall({**row, "status": status}))
