"""Time the campaign actually spent: wall clock, not the sum of lanes that ran
side by side. Split from `test_watchdog` at the 200-line cap."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from test_watchdog import space
from watchdog import already_said, check

EXPECTED_TESTS = 7


class TimeTest(unittest.TestCase):
    """Time is what a campaign spends; money is only written down."""

    def test_a_queued_rebuild_is_progress_and_restarts_the_clock(self):
        """Two green gates and two verdicts in three hours is a hard task
        moving, not a loop going through the motions."""
        here = space()
        for _ in range(3):
            here.event("step", task="T1", step="build", seconds=3600.0)
        here.event("rebuild_queued", task="T1", round=1, why="one finding")
        here.event("step", task="T1", step="build", seconds=1800.0)
        self.assertFalse(check(here, hours_ceiling=2.0).futile)

    def test_futility_is_said_once_until_the_next_progress(self):
        """The driver says it where the red-flag check shows it, then carries
        on; a second turn without progress must not say it again."""
        here = space()
        for _ in range(3):
            here.event("step", task="T1", step="build", seconds=3600.0)
        self.assertFalse(already_said(here))            # nothing said yet
        here.event("blocked", why="3.0 hours of work and nothing accepted")
        self.assertTrue(already_said(here))             # said; do not repeat
        here.event("rebuild_queued", task="T1", round=1, why="one finding")
        self.assertFalse(already_said(here))            # progress: may say it again

    def test_hours_of_work_with_nothing_accepted_trips_the_breaker(self):
        # Three hours of work, one after another — the campaign's own clock.
        class Rows:
            def events(self):
                return [{"kind": "step", "task": "T1", "step": "build", "seconds": 3600,
                         "at": f"2026-08-30T{10 + n}:00:00Z"} for n in range(3)]
        verdict = check(Rows(), hours_ceiling=2.0)
        self.assertTrue(verdict.futile)
        self.assertIn("3.0 hours", verdict.why)

    def test_an_answered_call_whose_gate_failed_does_not_restart_the_clock(self):
        # The build call is recorded and counted BEFORE its own gate runs
        # (lib/loop_steps.py); under the old rule it alone reset this window
        # even though the round's gate then failed (lib/loop_judge.py),
        # hiding three hours of going-nowhere behind one answered call.
        class Rows:
            def events(self):
                return [{"kind": "step", "task": "T1", "step": "build", "seconds": 3600,
                         "at": f"2026-08-30T{10 + n}:00:00Z"} for n in range(3)] + [
                    {"kind": "attempt", "task": "T1", "outcome": "ok", "counted": True,
                     "failed_gate": False, "at": "2026-08-30T13:05:00Z"},
                    {"kind": "step", "task": "T1", "step": "gate", "passed": False,
                     "seconds": 30, "at": "2026-08-30T13:06:00Z"},
                    {"kind": "attempt", "task": "T1", "account": "gate", "outcome": "ok",
                     "counted": True, "failed_gate": True, "at": "2026-08-30T13:06:05Z"},
                ]
        verdict = check(Rows(), hours_ceiling=2.0)
        self.assertTrue(verdict.futile)
        self.assertIn("3.0 hours", verdict.why)

    def test_lanes_that_overlap_are_not_counted_twice(self):
        # Three lanes of one hour, side by side, are one hour of the campaign.
        class Rows:
            def events(self):
                return [{"kind": "step", "task": f"T{n}", "step": "build", "seconds": 3600,
                         "at": "2026-08-30T11:00:00Z"} for n in range(3)]
        self.assertFalse(check(Rows(), hours_ceiling=2.0).futile)

    def test_time_spent_waiting_is_not_time_wasted(self):
        here = space()
        for _ in range(20):
            here.event("idle", waiting=["T4"], unfinished=["T4"], sleep=300)
        self.assertFalse(check(here, hours_ceiling=1.0).futile)

    def test_the_clock_restarts_at_every_acceptance(self):
        here = space()
        here.event("step", task="T1", step="build", seconds=7200)
        here.event("accepted", task="T1")
        here.event("step", task="T2", step="build", seconds=600)
        self.assertFalse(check(here, hours_ceiling=1.0).futile)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
