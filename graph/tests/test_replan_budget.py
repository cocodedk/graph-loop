"""Replanning stops for repetition or six rounds, never for new findings alone."""

import tempfile
import unittest
from unittest.mock import Mock

import tmp_root  # noqa: F401 — keep temporary test repositories under the suite's root
from backlog_decision import can_replan
from backlog_status import is_wall
from replan import replan, replan_until_planned
from replan_budget import MAX_ROUNDS, same_complaint, stop_reason
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

    def test_varying_refusals_stop_at_six_and_alert_names_the_ceiling(self):
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
        self.assertIn("the ceiling", space.alerts(unread_only=False)[-1])
        self.assertNotIn("the same complaint twice", space.alerts(unread_only=False)[-1])

    def test_repetition_alert_names_the_shape_and_is_not_duplicated(self):
        book = book_with(replans=1, replan_history=[REASONS[0]], refused_why=REASONS[0])
        space = Workspace(tempfile.mkdtemp()).init(goal="test", backlog=str(book.path))
        planner = Mock()
        self.assertFalse(replan_until_planned(book, book.task("T1"), planner, space=space).rewritten)
        self.assertFalse(replan_pending(book, space, planner))
        planner.assert_not_called()
        self.assertEqual(1, len(space.alerts(unread_only=False)))
        self.assertIn("the same complaint twice", space.alerts(unread_only=False)[0])
