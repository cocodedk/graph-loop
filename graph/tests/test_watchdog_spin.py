"""A spinning verdict names its task, and a quarantine spends the endings
before it. `test_watchdog` holds the rest; this file exists because that one
is at the 200-line cap."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from test_watchdog import space
from watchdog import already_said, check

EXPECTED_TESTS = 11


class SpinTaskTest(unittest.TestCase):
    def test_the_verdict_names_the_task_that_spun_not_the_one_that_ran_last(self):
        here = space()
        for _ in range(2):
            here.event("failed", task="T7", step="gate", why="bash: gates/x.sh: No such file")
        here.event("refused", task="T2", step="contract", why="unrelated")
        verdict = check(here)
        self.assertTrue(verdict.spinning)
        self.assertEqual("T7", verdict.task)

    def test_endings_before_a_quarantine_are_spent(self):
        here = space()
        for _ in range(2):
            here.event("failed", task="T7", step="gate", why="bash: gates/x.sh: No such file")
        here.event("quarantined", task="T7", why="…")
        self.assertFalse(check(here).spinning)

    def test_endings_before_a_spin_spent_are_spent(self):
        # The boundary is the last DECISION about the spin, whether the write
        # was a quarantine or skipped because the card had already settled or
        # been sliced (graph-goal.py) — either way the endings before it are
        # spent, or check() replays the same stale spin forever.
        here = space()
        for _ in range(2):
            here.event("failed", task="T7", step="gate", why="bash: gates/x.sh: No such file")
        here.event("spin_spent", task="T7", why="…")
        self.assertFalse(check(here).spinning)

    def test_an_applied_decision_spends_the_endings_it_answered(self):
        # A rewrite or a requeue is a recovery, like a replan: the card runs on
        # under the same id, and counting the failures the decision answered
        # would quarantine it on its first new one. It gives back no decision
        # budget — that is counted on disk, per request, not from this log.
        here = space()
        for _ in range(2):
            here.event("failed", task="T7", step="gate", why="bash: gates/x.sh: No such file")
        here.event("decided", task="T7", decision="rewrite", why="the gate could never fail")
        self.assertFalse(check(here).spinning)

    def test_one_tasks_boundary_does_not_spend_another_tasks_endings(self):
        # A global cut once let T1's spin_spent erase T2's earlier ending
        # too, so T2's own second identical failure went uncounted. The
        # boundary must spend the endings of ITS OWN task only.
        here = space()
        here.event("failed", task="T2", step="gate", why="bash: gates/y.sh: No such file")
        here.event("failed", task="T1", step="gate", why="bash: gates/x.sh: No such file")
        here.event("spin_spent", task="T1", why="…")
        here.event("failed", task="T2", step="gate", why="bash: gates/y.sh: No such file")
        verdict = check(here)
        self.assertTrue(verdict.spinning)
        self.assertEqual("T2", verdict.task)


    def test_endings_before_a_replan_are_spent(self):
        # A rewritten contract answers the refusals that asked for it, exactly
        # as it answers them for `needs_slice` (`spends_failures`). Both
        # readers must count from the same boundary, or the turn that rewrites
        # a card quarantines it on the same breath.
        here = space()
        for _ in range(2):
            here.event("refused", task="T7", step="contract", why="the gate proves nothing")
        here.event("replanned", task="T7", why="rewritten")
        self.assertFalse(check(here).spinning)


class SameEndingTest(unittest.TestCase):
    def test_two_reasons_sharing_a_long_prefix_are_not_the_same_ending(self):
        # Gate output is kept as its last 400 characters (loop_judge.py); a
        # 120-character prefix of that tail is shared by whole families of
        # different failures, and each collision is a card parked for a spin
        # that never happened.
        here = space()
        for tail in ("first assertion", "a different one"):
            here.event("failed", task="T7", step="gate", why="x" * 120 + tail)
        self.assertFalse(check(here).spinning)

    def test_the_same_failure_with_a_ticking_counter_is_the_same_ending(self):
        # A unittest gate's tail carries its own elapsed time, so the same
        # failure never reads the same twice and the spin is never seen.
        here = space()
        for seconds in ("12.345", "12.901"):
            here.event("failed", task="T7", step="gate",
                       why=f"Ran 1028 tests in {seconds}s\n\nFAILED (failures=1)")
        self.assertTrue(check(here).spinning)


class SaidOnceTest(unittest.TestCase):
    def test_a_passed_gate_lets_a_later_stall_be_said_again(self):
        # The stuck window restarts at a task's own gate going green; so must
        # the "said once" rule, or a second, separate stall is never alerted.
        here = space()
        here.event("blocked", why="3 turns finished and nothing was accepted")
        self.assertTrue(already_said(here))
        here.attempt("T1", account="work", kind="ok", cost=1.0)
        with here.step("T1", "gate") as note:
            note(passed=True)
        self.assertFalse(already_said(here))
        here.event("blocked", why="3 turns finished and nothing was accepted")
        self.assertTrue(already_said(here))

    def test_a_failed_gate_does_not_let_a_stall_be_said_again(self):
        # The real shape of a failed round (lib/loop_steps.py, lib/loop_judge.py):
        # an answered build call is recorded — and counted — BEFORE its gate
        # even runs, so that call alone must not fool `already_said` into
        # thinking the stall ended; only the gate's own step, passing, does.
        here = space()
        here.event("blocked", why="3 turns finished and nothing was accepted")
        self.assertTrue(already_said(here))
        here.attempt("T1", account="work", kind="ok", cost=1.0)   # answered build call
        with here.step("T1", "gate") as note:
            note(passed=False)                                    # its gate failed
        here.attempt("T1", account="gate", kind="ok", failed_gate=True)  # loop_judge.py's own record
        self.assertTrue(already_said(here))     # still said: no gate of this task passed
        here.attempt("T1", account="work", kind="ok", cost=1.0)
        with here.step("T1", "gate") as note:
            note(passed=True)                                     # this one's gate passed
        self.assertFalse(already_said(here))    # a passed gate is progress


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
