"""Catching a loop that is busy and getting nowhere.

Written before `watchdog.py`. Three shapes of nothing, all seen or paid for:
the same task ending the same way again and again; a run of turns with no task
finished; and hours or answered attempts running on with no progress in them.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from watchdog import check
from workspace import Workspace

EXPECTED_TESTS = 15


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="b.yaml")


class RepeatTest(unittest.TestCase):
    def test_the_same_task_refused_the_same_way_twice_is_a_spin(self):
        here = space()
        for _ in range(2):
            here.event("refused", task="T1", step="contract", why="the gate proves nothing")
        verdict = check(here)
        self.assertTrue(verdict.spinning)
        self.assertIn("T1", verdict.why)
        self.assertIn("contract", verdict.why)

    def test_the_same_task_refused_for_different_reasons_is_not_a_spin(self):
        here = space()
        here.event("refused", task="T1", step="contract", why="too broad")
        here.event("refused", task="T1", step="red_first", why="the gate already passes")
        self.assertFalse(check(here).spinning)

    def test_different_tasks_refused_alike_is_not_a_spin(self):
        here = space()
        here.event("refused", task="T1", step="contract", why="the gate proves nothing")
        here.event("refused", task="T2", step="contract", why="the gate proves nothing")
        self.assertFalse(check(here).spinning)


class ProgressTest(unittest.TestCase):
    def test_three_turns_with_nothing_accepted_is_no_progress(self):
        here = space()
        for task_id in ("T1", "T2", "T3"):
            here.event("claimed", task=task_id)
            here.event("released", task=task_id)
        verdict = check(here)
        self.assertTrue(verdict.stuck)
        self.assertIn("3 turns", verdict.why)

    def test_an_accepted_task_clears_the_count(self):
        here = space()
        for task_id in ("T1", "T2"):
            here.event("claimed", task=task_id)
            here.event("released", task=task_id)
        here.event("accepted", task="T3")
        here.event("claimed", task="T4")
        here.event("released", task="T4")
        self.assertFalse(check(here).stuck)

    def test_waiting_for_a_human_or_a_limit_is_not_being_stuck(self):
        here = space()
        for _ in range(4):
            here.event("idle", waiting=["T4"], unfinished=["T4"], sleep=300)
        self.assertFalse(check(here).stuck)


class CodexFindingsTest(unittest.TestCase):
    def test_the_release_of_an_accepted_turn_is_not_counted_against_the_limit(self):
        here = space()
        here.event("claimed", task="T1"); here.event("accepted", task="T1")
        here.event("released", task="T1")            # the accepted turn's own release
        for task_id in ("T2", "T3"):
            here.event("claimed", task=task_id); here.event("released", task=task_id)
        self.assertFalse(check(here).stuck)

    def test_a_gate_failure_is_visible_to_the_watchdog(self):
        here = space()
        for _ in range(2):
            here.event("failed", task="T1", step="gate", why="two tests still red")
        self.assertTrue(check(here).spinning)

    def test_reaching_the_attempt_ceiling_exactly_trips_it(self):
        here = space()
        for _ in range(3):
            here.attempt("T1", account="work", kind="ok")
        self.assertTrue(check(here, attempt_ceiling=3).futile)


class FutileTest(unittest.TestCase):
    """Effort, never money: cost is logged, and decides nothing."""

    def test_many_answered_attempts_with_nothing_accepted_trips_the_breaker(self):
        here = space()
        for _ in range(4):
            here.attempt("T1", account="work", kind="ok", cost=99.0)
        verdict = check(here, attempt_ceiling=4)
        self.assertTrue(verdict.futile)
        self.assertIn("4 answered attempts", verdict.why)
        self.assertNotIn("$", verdict.why)

    def test_attempts_that_bought_accepted_work_are_fine(self):
        here = space()
        for _ in range(6):
            here.attempt("T1", account="work", kind="ok", cost=2.0)
            here.event("accepted", task="T1")
        self.assertFalse(check(here, attempt_ceiling=4).futile)

    def test_calls_that_never_happened_do_not_count_toward_it(self):
        here = space()
        for _ in range(9):
            here.attempt("T1", account="work", kind="limit")
        self.assertFalse(check(here, attempt_ceiling=4).futile)

    def test_a_rebuild_queued_resets_the_attempt_ceiling_window_too(self):
        # already_said resets at ANY progress — accepted, rebuild_queued, or a
        # passed gate — but this ceiling used to count only since the last
        # acceptance: a rebuild_queued left it counting stale, pre-rebuild
        # attempts, so it could trip (or already_said could say the alert
        # again) right after the campaign had just moved.
        here = space()
        for _ in range(2):
            here.attempt("T1", account="work", kind="ok", cost=1.0)
        here.event("rebuild_queued", task="T1", round=1, why="one finding")
        here.attempt("T1", account="work", kind="ok", cost=1.0)
        self.assertFalse(check(here, attempt_ceiling=3).futile)



class ProgressIsProgressTest(unittest.TestCase):
    def test_a_build_that_answered_and_passed_its_gate_resets_the_turn_count(self):
        # A task can take three turns and still be moving; only turns since the
        # last sign of life count. Seen live: eleven old refusals condemned a
        # task whose builder had just finished its work. The answered build
        # call alone is not that sign — its gate passing is (lib/loop_judge.py).
        here = space()
        for task_id in ("T1", "T2"):
            here.event("claimed", task=task_id); here.event("released", task=task_id)
        here.attempt("T3", account="work", kind="ok", cost=2.7)
        with here.step("T3", "gate") as note:
            note(passed=True)
        here.event("claimed", task="T3"); here.event("released", task="T3")
        self.assertFalse(check(here).stuck)



class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
