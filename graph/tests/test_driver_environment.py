"""The first missing toolchain stops this run, without the watchdog or another card."""

from __future__ import annotations

import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from gates import GateResult
from loop_environment import environment_stop
from test_driver import graph_goal
from test_gate_environment import SDK
from test_loop import Fakes, loop_for, task


class DriverEnvironmentTest(unittest.TestCase):
    def test_first_sdk_failure_stands_down_once_without_charging_either_card(self):
        loop, book, space = loop_for(task(gate="./gradlew test", rebuild_round=2),
                                     Fakes(), [task(id="T2")])
        space.event("driver_started")
        before = book.tasks()
        args = types.SimpleNamespace(dry_run=False, lanes=1, max_tasks=2,
                                     idle_seconds=1, attempt_ceiling=12, hours_ceiling=2)
        with mock.patch.object(graph_goal, "Loop", return_value=loop), \
             mock.patch.object(graph_goal, "alert_cwd"), \
             mock.patch.object(graph_goal, "turn_opens", return_value=None), \
             mock.patch.object(graph_goal, "after_lanes") as after, \
             mock.patch("gates.run_gate", return_value=GateResult(1, SDK)), \
             mock.patch.object(space, "idle") as idle:
            code = graph_goal._run(args, space)
        self.assertEqual(78, code)  # the supervisor's existing deliberate stand-down exit
        for old, new in zip(before, book.tasks()):
            self.assertEqual(old["status"], new["status"])
            self.assertEqual(old.get("rebuild_round"), new.get("rebuild_round"))
            self.assertEqual(old.get("gate_rounds"), new.get("gate_rounds"))
        self.assertEqual(before[1], book.task("T2"))
        after.assert_not_called()
        idle.assert_not_called()
        environment_stop(space)  # repeating the read cannot repeat the alert
        rows = space.events()
        self.assertEqual(["T1"], [row["task"] for row in rows if row["kind"] == "claimed"])
        alerts = [row for row in rows if row["kind"] == "alert"]
        self.assertEqual(1, len(alerts))
        self.assertIn("ANDROID_HOME", alerts[0]["why"])
        self.assertEqual(1, sum(row["kind"] == "driver_stood_down" for row in rows))
        self.assertFalse(any(row["kind"] in ("failed", "rejected", "quarantined") for row in rows))

    def test_a_new_run_does_not_stop_on_the_previous_runs_environment_ending(self):
        _, _, space = loop_for(task(), Fakes())
        space.event("environment", task="T1", remedy="set JAVA_HOME")
        space.event("driver_started")
        self.assertEqual("", environment_stop(space))
