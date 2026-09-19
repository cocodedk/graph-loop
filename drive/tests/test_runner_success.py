"""A job a successful command left running dies with the call that started it.

`run` killed the child's whole process group on a timeout and on an interrupt,
but not when the command simply returned. A gate's trailing `&`, or a model
CLI's own helper, that had detached this call's pipes kept running — and kept
writing into the tree — while the caller read the output and moved on to
review or publication (finding 6 of the 2026-09-08 review).
"""

from __future__ import annotations

import os
import pathlib
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from runner import run

EXPECTED_TESTS = 4


def gone(pid: int) -> bool:
    """Nothing answers to `pid` any more — a negative `pid` asks about that
    whole process group, the way `os.killpg` does."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class LeftBehindJob:
    """A command that returns 0 while a job it started keeps running. The job
    detaches this call's pipes, so `communicate` reaches EOF and `run` returns
    with the job still alive; the job writes its own pid and the command waits
    for it, so a job that never started cannot pass by being absent. The
    temporary directory and the group both end with the test."""

    def __init__(self, case: unittest.TestCase) -> None:
        self.case = case
        tmp = pathlib.Path(case.enterContext(tempfile.TemporaryDirectory()))
        self.leader, self.job = tmp / "leader", tmp / "job"
        self.argv = ["bash", "-c",
                     (f"echo $$ > {self.leader}; "
                      f"(exec </dev/null >/dev/null 2>&1; "
                      f"echo $BASHPID > {self.job}; exec sleep 300) & "
                      f"until [ -s {self.job} ]; do sleep 0.01; done")]

    def pids(self) -> tuple[int, int]:
        """The group's pid and the job's, once the command has answered."""
        pgid, job_pid = int(self.leader.read_text()), int(self.job.read_text())
        self.case.addCleanup(kill_group, pgid)   # a failing run leaves nothing behind
        return pgid, job_pid


class SuccessTest(unittest.TestCase):
    def test_a_background_job_does_not_outlive_a_successful_call(self):
        left = LeftBehindJob(self)
        done = run(left.argv, timeout=30)
        pgid, job_pid = left.pids()
        self.assertEqual(0, done.returncode)
        self.assertTrue(gone(job_pid), "the background job outlived the call that started it")
        self.assertTrue(gone(-pgid), "the group outlived the call that started it")


class InterruptedCleanupTest(unittest.TestCase):
    def test_a_ctrl_c_during_the_cleanup_still_kills_the_group(self):
        """The cleanup is not outside the interrupt handler: a SIGINT that
        lands while the group is being ended is the interrupt path's to
        finish, or the driver walks away from a job it started."""
        left = LeftBehindJob(self)
        with (patch("runner.terminate_group", side_effect=KeyboardInterrupt),
              self.assertRaises(KeyboardInterrupt)):
            run(left.argv, timeout=30)
        pgid, job_pid = left.pids()
        self.assertTrue(gone(job_pid), "the job outlived the interrupted cleanup")
        self.assertTrue(gone(-pgid), "the group outlived the interrupted cleanup")


class FailedCleanupTest(unittest.TestCase):
    def test_a_group_that_outlived_the_kill_is_not_a_success(self):
        """`terminate_group` answers whether the group is actually gone. A
        call that hands back output while its children still run has not
        succeeded, and the caller must hear it: `gates.run_gate` already
        reads `OSError` as a crashed gate."""
        with (patch("runner.terminate_group", return_value=False),
              self.assertRaises(OSError)):
            run(["bash", "-c", "echo done"], timeout=30)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
