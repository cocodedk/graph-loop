"""`--check` must shout about the two states that stop the campaign.

It said "no red flags" while nothing was left to restart the driver: the two
lines that say so lived in the screen's health section, and `red_flags` read
only the warnings and the alerts.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import view
import view_pulse

PS = [(None, ["1", "0:01", "bash", "-c", "true"])]
SUPERVISOR = [("supervisor", ["1", "0:01", "bash", "supervisor.sh"])]


EXPECTED_TESTS = 5


class TheCheapLookSeesTheWorstStates(unittest.TestCase):
    def setUp(self):
        self.campaign = pathlib.Path(tempfile.mkdtemp())
        # the campaign names its own supervisor by pid, as supervisor.sh does
        # when it takes the lock: a name on the process list is not evidence
        (self.campaign / "supervisor.pid").write_text("1", "utf-8")
        patch = unittest.mock.patch.object(view_pulse, "CAMPAIGN", self.campaign)
        patch.start()
        self.addCleanup(patch.stop)
        healthy = unittest.mock.patch.object(view_pulse, "disk_free_gb", lambda path: 300.0)
        healthy.start()                                       # the host's real disk is not the subject
        self.addCleanup(healthy.stop)

    def test_a_dead_supervisor_is_a_red_flag(self):
        self.assertTrue(any("SUPERVISOR IS NOT RUNNING" in line
                            for line in view_pulse.health_failures(PS)))

    def test_a_stop_flag_is_a_red_flag(self):
        (self.campaign / "stop.flag").touch()
        self.assertTrue(any("STOP FLAG IS SET" in line
                            for line in view_pulse.health_failures(SUPERVISOR)))

    def test_a_live_supervisor_and_no_stop_flag_say_nothing(self):
        self.assertEqual(view_pulse.health_failures(SUPERVISOR), [])

    def test_a_nearly_full_disk_is_a_red_flag(self):
        # the full disk of 2026-09-03 killed every process with no warning
        with unittest.mock.patch.object(view_pulse, "disk_free_gb", lambda path: 3.0):
            self.assertTrue(any("DISK NEARLY FULL" in line
                                for line in view_pulse.health_failures(SUPERVISOR)))
        with unittest.mock.patch.object(view_pulse, "disk_free_gb", lambda path: 300.0):
            self.assertEqual(view_pulse.health_failures(SUPERVISOR), [])

    def test_red_flags_asks_the_same_function_the_screen_does(self):
        with unittest.mock.patch.object(view, "health_failures",
                                        return_value=["  SUPERVISOR IS NOT RUNNING"]), \
             unittest.mock.patch.object(view, "warnings", return_value=[]), \
             unittest.mock.patch.object(view, "alerts", return_value=[]):
            self.assertEqual(view.red_flags(), ["  SUPERVISOR IS NOT RUNNING"])


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
