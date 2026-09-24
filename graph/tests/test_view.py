"""The dashboard's red flags: what must shout, and what must stay quiet."""

from __future__ import annotations

import pathlib
import sys
import time
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from view_health import (
    _driver_pid,
    _driver_start,
    driver_knows_flag,
    driver_missing,
    is_loop_process,
    restart_grace,
    stale_driver_line,
    supervisor_counts_quick_exits,
    supervisor_owns_driver,
    supervisor_restart_aware,
)

EXPECTED_TESTS = 21


class DriverMissingTest(unittest.TestCase):
    """The two facts are handed in — is THIS campaign's supervisor up, is its
    own driver running — never read off the host's process list, where another
    campaign's pair answered for ours (round-4 finding 15,
    test_health_reads_this_campaigns_own_processes.py)."""

    def test_no_driver_long_after_an_exit_is_a_red_flag(self):
        flag = driver_missing(True, False, "driver exited rc=143 after 1556s", exited_seconds_ago=300)
        self.assertIn("no driver", flag)

    def test_the_supervisors_restart_pause_is_not_a_flag(self):
        self.assertEqual("", driver_missing(True, False, "driver exited rc=143 after 1556s",
                                            exited_seconds_ago=40))

    def test_a_running_driver_is_no_flag(self):
        self.assertEqual("", driver_missing(True, True, "starting the driver",
                                            exited_seconds_ago=3000))


class RestartGraceTest(unittest.TestCase):
    """The grace follows supervisor.sh: 60 s per consecutive immediate failure
    (an exit under 30 s), at most four, plus a minute of slack; a normal exit
    gets one pause; five immediate failures mean it stood down — no grace."""

    def test_a_normal_exit_gets_the_plain_pause(self):
        self.assertEqual(120, restart_grace(["starting the driver", "driver exited rc=143 after 1556s"]))

    def test_consecutive_immediate_failures_back_off_like_the_supervisor(self):
        log = ["driver exited rc=1 after 3s", "starting the driver", "driver exited rc=1 after 2s",
               "starting the driver", "driver exited rc=1 after 4s"]
        self.assertEqual(60 * 3 + 60, restart_grace(log))

    def test_the_backoff_never_exceeds_the_supervisors_fourth_pause(self):
        log = ["driver exited rc=1 after 1s"] * 9
        self.assertEqual(60 * 4 + 60, restart_grace(log))

    def test_standing_down_means_no_grace_at_all(self):
        log = ["driver exited rc=1 after 1s", "five immediate failures: standing down for a person"]
        self.assertEqual(0, restart_grace(log))
        self.assertIn("no driver", driver_missing(True, False, log[-1], exited_seconds_ago=1))


class LoopProcessTest(unittest.TestCase):
    """Only the driver's `run` and the supervisor count; the supervisor's own
    `report` snapshot, an editor on the script, or a grep do not."""

    def test_the_driver_is_graph_goal_run(self):
        self.assertEqual("driver", is_loop_process(["2", "00:05", "python3", "/x/graph-goal.py", "run", "--idle-seconds", "300"]))
        self.assertEqual("", is_loop_process(["3", "00:01", "python3", "/x/graph-goal.py", "report"]))

    def test_the_supervisor_is_bash_on_its_script(self):
        self.assertEqual("supervisor", is_loop_process(["1", "00:05", "bash", "/x/supervisor.sh"]))
        self.assertEqual("", is_loop_process(["4", "00:05", "vim", "supervisor.sh"]))


class DriverStartTest(unittest.TestCase):
    def test_the_report_snapshot_is_not_the_driver(self):
        rows = [["4", "9", "python3", "/x/graph-goal.py", "report"]]
        self.assertIsNone(_driver_start(rows, [{"kind": "driver_started", "pid": 4}]))
        rows.append(["41", "9", "python3", "/x/graph-goal.py", "run"])
        started = _driver_start(rows, [{"kind": "driver_started", "pid": 41}])
        self.assertIsNotNone(started)

    def test_the_start_is_this_campaigns_driver_not_the_hosts_first(self):
        rows = [["33", "9000", "python3", "/y/graph-goal.py", "run"],       # another campaign's driver, old
                ["41", "9", "python3", "/x/graph-goal.py", "run"]]           # ours, just started
        started = _driver_start(rows, [{"kind": "driver_started", "pid": 41}])
        self.assertLess(time.time() - started, 60)
        # a campaign that never announced a driver is on a pre-brick one: the host's
        # driver is read, so the rollout advice can be shown for it
        self.assertGreater(time.time() - _driver_start(rows, []), 8000)
        self.assertIsNone(_driver_start(rows, [{"kind": "driver_started", "pid": 99}]))   # announced and gone

class SupervisorRestartTest(unittest.TestCase):
    def test_a_supervisor_start_resets_the_failure_count(self):
        log = ["driver exited rc=1 after 1s", "driver exited rc=1 after 1s", "driver exited rc=1 after 1s",
               "supervisor started", "starting the driver", "driver exited rc=1 after 2s"]
        self.assertEqual(120, restart_grace(log))


class RolloutTest(unittest.TestCase):
    def test_a_driver_that_predates_the_flag_is_switched_by_the_stop_flag(self):
        line = stale_driver_line(12, False, "/c/restart.flag")
        self.assertIn("`touch /c/stop.flag`", line)                    # the old driver knows the stop flag
        self.assertIn("start `bash graph/supervisor.sh`", line)
        self.assertIn("Never kill it", line)
        self.assertIn("`touch /c/restart.flag`", stale_driver_line(12, True, "/c/restart.flag"))

    def test_the_driver_pid_is_this_campaigns_announced_driver_not_the_hosts_first(self):
        rows = [["4", "9", "python3", "/x/graph-goal.py", "report"],
                ["33", "9", "python3", "/y/graph-goal.py", "run"],                 # another campaign's driver, first on the host
                ["41", "9", "python3", "/x/graph-goal.py", "run", "--idle-seconds", "300"],
                ["7", "1", "bash", "/x/supervisor.sh"]]
        ours = [{"kind": "driver_started", "pid": 41}]
        self.assertEqual(41, _driver_pid(rows, ours))
        self.assertIsNone(_driver_pid(rows, [{"kind": "driver_started", "pid": 4}]))    # announced, but that pid is the report
        self.assertEqual(33, _driver_pid(rows, []))                                       # none announced: a pre-brick driver, the host's
        self.assertIsNone(_driver_pid(rows, [{"kind": "driver_started", "pid": 99}]))   # announced and gone
        with unittest.mock.patch("view_health._started", return_value="boot-a:100"):
            self.assertEqual(41, _driver_pid(rows, [{"kind": "driver_started", "pid": 41, "started": "boot-a:100"}]))
            self.assertIsNone(_driver_pid(rows, [{"kind": "driver_started", "pid": 41, "started": "boot-a:7"}]))   # the pid reused

    def test_a_supervisor_counts_only_when_it_owns_the_driver_and_knows_the_restart_exit(self):
        sup = ["7", "1", "1000", "bash", "/x/supervisor.sh"]
        child = ["41", "7", "9", "python3", "/x/graph-goal.py", "run"]
        orphan = ["41", "1", "9", "python3", "/x/graph-goal.py", "run"]
        self.assertTrue(supervisor_owns_driver(41, [sup, child]))
        self.assertFalse(supervisor_owns_driver(41, [sup, orphan]))
        self.assertFalse(supervisor_owns_driver(41, [child]))
        report = ["42", "7", "2", "python3", "/x/graph-goal.py", "report"]             # the supervisor's own snapshot
        self.assertFalse(supervisor_owns_driver(42, [sup, report]))                      # a child, but not the driver
        other = ["99", "7", "9", "python3", "/y/graph-goal.py", "run"]                  # another campaign's pair
        self.assertFalse(supervisor_owns_driver(41, [sup, other, orphan]))
        self.assertFalse(supervisor_owns_driver(None, [sup, child]))
        self.assertTrue(supervisor_restart_aware(["x supervisor started, restart-aware", "x starting the driver"]))
        self.assertFalse(supervisor_restart_aware(["x supervisor started", "x starting the driver"]))
        self.assertFalse(supervisor_restart_aware([]))

    def test_only_a_driver_that_announced_itself_knows_the_flag(self):
        rows = [{"kind": "driver_started", "pid": 41}, {"kind": "claimed"}]
        self.assertTrue(driver_knows_flag(rows, 41))
        self.assertFalse(driver_knows_flag(rows, 42))
        self.assertFalse(driver_knows_flag(rows, None))

    def test_only_a_restart_aware_supervisor_spares_the_restart_exit(self):
        quick75 = ["x supervisor started"] + ["x driver exited rc=75 after 3s"] * 3
        self.assertEqual(3 * 60 + 60, restart_grace(quick75))      # an old supervisor counts all three as crashes
        aware = ["x supervisor started, restart-aware"] + ["x driver exited rc=75 after 3s"] * 3
        self.assertEqual(restart_grace(["x driver exited rc=0 after 900s"], restart_aware=True), restart_grace(aware))

    def test_a_supervisor_that_counts_quick_exits_no_longer_spares_a_quick_restart_exit(self):
        # B6: any exit under 30 s counts, rc 75 included — the counting
        # supervisor backs off on it like any crash loop, and the grace follows.
        counting = (["x supervisor started, restart-aware, quick exits counted"]
                    + ["x driver exited rc=75 after 0s"] * 3)
        self.assertEqual(3 * 60 + 60, restart_grace(counting))
        self.assertTrue(supervisor_counts_quick_exits(counting))
        self.assertFalse(supervisor_counts_quick_exits(["x supervisor started, restart-aware"]))
        after_a_real_turn = ["x supervisor started, restart-aware, quick exits counted",
                             "x driver exited rc=75 after 900s"]
        self.assertEqual(60 + 60, restart_grace(after_a_real_turn))   # 30 s or more, then a restart: no count

    def test_only_the_restart_exit_is_not_a_crash_in_the_grace(self):
        crashes = ["x driver exited rc=1 after 3s"] * 3
        self.assertGreater(restart_grace(crashes), restart_grace(["x driver exited rc=75 after 3s"] * 3, restart_aware=True))
        self.assertEqual(restart_grace(["x driver exited rc=75 after 3s"] * 3, restart_aware=True), restart_grace(["x driver exited rc=0 after 900s"]))
        # an OLD supervisor's log graded during the transition: it counted a
        # quick rc 0; the new one stands down instead (test_supervisor_stand_down)
        self.assertEqual(restart_grace(crashes), restart_grace(["x driver exited rc=0 after 3s"] * 3))

    def test_without_a_supervisor_the_advice_is_to_start_one(self):
        line = stale_driver_line(12, True, "/c/restart.flag", supervised=False)
        self.assertIn("NO restart-aware supervisor owns it", line)
        self.assertIn("`touch /c/stop.flag`", line)                 # the driver exits first …
        self.assertIn("then remove the stop flag and start `bash graph/supervisor.sh`", line)
        self.assertNotIn("restart.flag`", line)                     # … never a second driver beside a live one


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
