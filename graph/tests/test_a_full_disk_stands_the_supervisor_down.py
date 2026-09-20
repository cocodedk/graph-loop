"""A disk about to fill stands the supervisor down; it is not a second mailbox.

The full disk of 2026-09-03 killed every process on the host, so the board
shouts about it — but the warning was ALSO a route to the owner of its own, mailed
by `stale_flags` while the loop kept running: a fourth human route, against
CLAUDE.md § Code, which leaves exactly one (a dead loop, infrastructure). The
disk now does what a dead loop does — the supervisor starts no driver, writes
its stand-down with the disk words inside it, delivers it and retries until it
lands — and `notice.fatal`, the one reading the messenger and the 15-minute
escalation share, knows only that stand-down (astra round 4, finding 16).

`run_supervisor` comes from test_supervisor_stand_down.py, the front door of
this rig.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import notice
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_supervisor_stand_down import run_supervisor

EXPECTED_TESTS = 4

WARNING = "  DISK NEARLY FULL — 3.1 GB free where the worktrees live (floor 20.0 GB)"


class FatalIsTheStandDownAloneTest(unittest.TestCase):
    def test_a_disk_warning_on_its_own_reaches_nobody(self):
        self.assertFalse(notice.fatal(WARNING), "the board's disk line mails the owner by itself")

    def test_the_stand_down_it_causes_does_reach_him(self):
        stood_down = ("  !! the supervisor stood down: DISK NEARLY FULL where the worktrees "
                      "live   (stood down 2026-09-09T10:00:00+0200, supervisor 4242)")
        self.assertTrue(notice.fatal(stood_down))
        self.assertIn(notice.DISK, stood_down)     # the words are inside the one route


class DiskStandsItDownTest(unittest.TestCase):
    def test_a_full_disk_starts_no_driver_and_says_so_in_its_notice(self):
        log, code, camp = run_supervisor(self, run_exit=0, disk_full=True)
        self.assertEqual(1, code)                               # a loop that gave up
        self.assertNotIn("starting the driver", log)            # nothing was started on it
        told = (camp / "prompt.txt").read_text("utf-8")         # what the messenger carried
        self.assertIn("the supervisor stood down", told)
        self.assertIn(notice.DISK, told)
        self.assertIn("standing down", log.strip().splitlines()[-1])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
