"""The plan phase runs before every driver.

The fresh review of PR #37, finding 2: the supervisor only ever ran
`graph-goal.py run`, and nothing anywhere ran `plan` except a person. A card the
build phase parked has no other actor, so the driver stood down on the same
queue every time — and five of those quick exits are an email to a person saying
the driver died.

The rig is `test_supervisor_stand_down`'s: the real supervisor.sh against a
stubbed driver, which stays the front door for it.
"""

from __future__ import annotations

import pathlib
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_supervisor_stand_down import run_supervisor

EXPECTED_TESTS = 3


class PlanPhaseTest(unittest.TestCase):
    def test_the_plan_phase_runs_before_the_driver(self):
        log, _, _ = run_supervisor(self, run_exit=0)
        self.assertEqual(1, log.count("planning"))
        self.assertLess(log.index("planning"), log.index("starting the driver"))

    def test_every_restarted_driver_is_planned_for_first(self):
        log, _, _ = run_supervisor(self, run_exit=75)
        self.assertEqual(5, log.count("starting the driver"))
        self.assertEqual(5, log.count("planning"))   # one each, never once at the start


    def test_the_log_carries_the_plan_phase_s_real_exit_code(self):
        """It was read as `rc=$?` inside the same line as `$(date -Is)`, which
        expands first and is itself a command, so every plan phase was logged
        rc=0 — including the 78 that says the graph still has a gap."""
        log, _, _ = run_supervisor(self, run_exit=0, plan_exit=78)
        self.assertIn("plan phase exited rc=78", log)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
