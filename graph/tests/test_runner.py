"""One shared process runner, and the one place a timeout actually kills.

Written after a reviewer's proof that `subprocess.run(..., timeout=)` leaves
a gate's or a model call's background job running: it kills only the direct
child, and whatever that child spawned with `&` keeps writing after the
caller has already moved on.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from runner import run

EXPECTED_TESTS = 5


def marker_command(marker: pathlib.Path) -> list[str]:
    """A background job that outlives a 1s timeout unless its group dies too."""
    return ["bash", "-c", f"(sleep 5; echo late > {marker}) & sleep 30"]


def term_resistant_command(marker: pathlib.Path, pidfile: pathlib.Path) -> list[str]:
    """A background job that ignores SIGTERM outright and has detached its own
    stdio, so the direct child's pipes close — ending `communicate` — while
    this keeps running underneath it. `pidfile` carries the group's pid out,
    since `run` never hands the caller a pid to check on."""
    return ["bash", "-c",
            (f"echo $$ > {pidfile}; "
             f"(trap '' TERM; exec </dev/null >/dev/null 2>&1; "
             f"sleep 30; echo late > {marker}) & sleep 30")]


def group_gone(pid: int) -> bool:
    """`os.killpg` raises once no process answers to `pid`'s group any more."""
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    return False


class TimeoutTest(unittest.TestCase):
    def test_a_timeout_kills_the_whole_group_not_just_the_direct_child(self):
        marker = pathlib.Path(tempfile.mkdtemp()) / "late"
        with self.assertRaises(subprocess.TimeoutExpired):
            run(marker_command(marker), timeout=1)
        time.sleep(6)   # long enough for the background job to have written, if it survived
        self.assertFalse(marker.exists(), "the background job outlived its group")

    def test_a_fast_command_returns_its_stdout_unchanged(self):
        out = run(["bash", "-c", "echo hello"], timeout=5)
        self.assertEqual("hello\n", out.stdout)
        self.assertEqual(0, out.returncode)

    def test_a_term_ignoring_child_is_gone_too_once_the_timeout_is_handled(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        marker, pidfile = tmp / "late", tmp / "pid"
        with self.assertRaises(subprocess.TimeoutExpired):
            run(term_resistant_command(marker, pidfile), timeout=1)
        time.sleep(1)
        self.assertFalse(marker.exists(), "the TERM-ignoring job outlived its group")
        self.assertTrue(group_gone(int(pidfile.read_text())),
                        "the group is still alive after the timeout was handled")


class InterruptTest(unittest.TestCase):
    def test_a_keyboard_interrupt_during_the_wait_still_kills_the_group(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        pidfile = tmp / "pid"
        argv = ["bash", "-c", f"echo $$ > {pidfile}; sleep 30"]

        def raise_once_the_child_is_up(*args, **kwargs):
            deadline = time.monotonic() + 5
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            raise KeyboardInterrupt()

        with (patch.object(subprocess.Popen, "communicate",
                           side_effect=raise_once_the_child_is_up),
              self.assertRaises(KeyboardInterrupt)):
            run(argv, timeout=5)
        self.assertTrue(group_gone(int(pidfile.read_text())),
                        "the group survived the interrupt")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
