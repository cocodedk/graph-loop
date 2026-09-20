"""A campaign's health is read from ITS OWN processes, never from a name.

`health_failures` called the supervisor alive when any `bash …/supervisor.sh`
was on the host, and `driver_missing` called the driver alive when any
`drive-goal.py run` was: campaign A's supervisor and driver could both be dead
while campaign B's kept A's board green (astra round 4, finding 15). The
supervisor writes its pid where its campaign can find it, the driver announces
its own (`driver_started`), and both readings ask those.
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
import view_health
import view_pulse

EXPECTED_TESTS = 4

# another campaign's pair, alive on this host, under the very names ours has
THEIRS = [["8001", "0:05", "bash", "/x/supervisor.sh"],
          ["8002", "0:05", "python3", "/x/drive-goal.py", "run", "--idle-seconds", "300"]]
OURS = ["4242", "0:05", "bash", "/y/supervisor.sh"]


class Campaign(unittest.TestCase):
    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        for module in (view, view_pulse, view_health):
            patch = unittest.mock.patch.object(module, "CAMPAIGN", self.camp)
            patch.start()
            self.addCleanup(patch.stop)
        healthy = unittest.mock.patch.object(view_pulse, "disk_free_gb", lambda path: 300.0)
        healthy.start()                          # the host's real disk is not the subject
        self.addCleanup(healthy.stop)

    def recorded(self, pid: str) -> None:
        (self.camp / "supervisor.pid").write_text(pid, "utf-8")


class SupervisorTest(Campaign):
    def test_another_campaigns_supervisor_does_not_answer_for_this_one(self):
        self.recorded("4242")                    # ours, and it is not among these
        lines = view_pulse.health_failures([(view_health.is_loop_process(p), p) for p in THEIRS])
        self.assertTrue(any("SUPERVISOR IS NOT RUNNING" in line for line in lines))

    def test_our_own_recorded_supervisor_says_nothing(self):
        self.recorded("4242")
        lines = view_pulse.health_failures(
            [(view_health.is_loop_process(p), p) for p in [*THEIRS, OURS]])
        self.assertEqual([], lines)


class DriverTest(Campaign):
    """The same reading for the driver: `driver_missing` is told whether THIS
    campaign's supervisor and driver are alive, and never shown a process
    list it would have to guess from."""

    def board(self, our_driver: int | None) -> list[str]:
        self.recorded("4242")

        class StubSpace:
            def __init__(self, *a): pass
            def events(self): return []
            def alerts(self): return []

        with unittest.mock.patch.object(view, "Workspace", StubSpace), \
             unittest.mock.patch.object(view_health, "_ps_rows", lambda: [OURS, *THEIRS]), \
             unittest.mock.patch.object(view, "health", lambda: ["  8002 0:05 python3 /x/drive-goal.py run"]), \
             unittest.mock.patch.object(view, "_supervisor_last_word",
                                        lambda: (["starting the driver"], 0.0)), \
             unittest.mock.patch.object(view, "base_measure", lambda *a, **k: ""), \
             unittest.mock.patch.object(view, "_driver_start", lambda *a, **k: None), \
             unittest.mock.patch.object(view, "_driver_pid", lambda *a, **k: our_driver), \
             unittest.mock.patch.object(view, "calls_in_flight", list), \
             unittest.mock.patch.object(view, "driver_is_working", lambda *a, **k: False), \
             unittest.mock.patch("doctor.diagnose", lambda *a, **k: []):
            return view.warnings()

    def test_another_campaigns_driver_does_not_answer_for_this_one(self):
        self.assertTrue(any("no driver is running" in line for line in self.board(None)))

    def test_our_own_announced_driver_silences_the_flag(self):
        self.assertEqual([], [line for line in self.board(4243) if "no driver" in line])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
