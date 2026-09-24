"""Stop always wins over a pending restart. Restart is consumed once; stop
persists; `idle()` only peeks at both flags: `restarting()` clears the flag it reports, `idle()` only
peeks at it so the next check still gets to act, and `stopping()` just
reads a plain file the loop can check between tasks.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from workspace import Workspace

EXPECTED_TESTS = 5


def fresh() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="backlog.yaml")


class StopTest(unittest.TestCase):
    def test_stop_wins_but_the_restart_flag_is_still_consumed(self):
        space = fresh()
        self.assertEqual("", space.stop_or_restart())
        (space.root / "restart.flag").touch()
        self.assertEqual("restart", space.stop_or_restart())
        (space.root / "restart.flag").touch(); space.stop()
        self.assertEqual("stop", space.stop_or_restart())
        self.assertFalse((space.root / "restart.flag").exists())

    def test_a_restart_flag_is_consumed_once_and_recorded(self):
        space = fresh()
        self.assertFalse(space.restarting())
        (space.root / "restart.flag").touch()
        self.assertTrue(space.restarting())
        self.assertFalse((space.root / "restart.flag").exists())   # the next driver must not stop again
        self.assertEqual("restart_requested", space.events()[-1]["kind"])
        self.assertFalse(space.restarting())

    def test_an_idle_wait_ends_early_on_a_flag_without_consuming_it(self):
        space = fresh()
        threading.Timer(1.5, (space.root / "restart.flag").touch).start()   # raised DURING the sleep
        started = time.monotonic()
        space.idle(30, slice_seconds=1)
        self.assertLess(time.monotonic() - started, 5)
        self.assertGreater(time.monotonic() - started, 1.4)
        self.assertTrue((space.root / "restart.flag").exists())

    def test_a_stop_is_a_file_the_loop_reads_between_tasks(self):
        space = fresh()
        self.assertFalse(space.stopping())
        space.stop()
        self.assertTrue(space.stopping())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
