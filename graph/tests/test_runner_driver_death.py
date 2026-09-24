"""A paid child dies with the driver that started it.

`start_new_session=True` puts every gate, model call and slicer in its own
session, so the driver's own death — a SIGKILL from a person, an OOM kill,
the full disk of 2026-09-03 — reaches none of them: the child is reparented
and keeps running and keeps spending, and a restarted driver can hand that
child's worktree to a second builder (finding 5 of the 2026-09-08 review,
round 2).
"""

from __future__ import annotations

import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 2
LIB = str(pathlib.Path(__file__).resolve().parents[1] / "lib")


def gone(pid: int) -> bool:
    """Nothing answers to `pid` any more. The driver is dead by then, so its
    child has been reaped by init: a survivor answers, a dead one does not."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class DriverDeathTest(unittest.TestCase):
    def test_a_child_does_not_outlive_the_driver_that_was_paying_for_it(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        pidfile, script = tmp / "child", tmp / "driver.py"
        # `exec sleep` — without it bash forks for the second command and the
        # pid written is bash's, so a test could pass on a dead shell while
        # the sleep it left behind ran on.
        script.write_text(
            "import sys\n"
            f"sys.path.insert(0, {LIB!r})\n"
            "from runner import run\n"
            f'run(["bash", "-c", "echo $$ > {pidfile}; exec sleep 300"], timeout=300)\n')
        driver = subprocess.Popen([sys.executable, str(script)])
        self.addCleanup(driver.wait)
        self.addCleanup(driver.kill)
        deadline = time.monotonic() + 20
        while not (pidfile.exists() and pidfile.read_text().strip()):
            self.assertLess(time.monotonic(), deadline, "the child never started")
            time.sleep(0.05)
        child = int(pidfile.read_text())
        self.addCleanup(kill, child)

        os.kill(driver.pid, signal.SIGKILL)
        driver.wait(timeout=10)
        end = time.monotonic() + 10
        while not gone(child) and time.monotonic() < end:
            time.sleep(0.05)
        self.assertTrue(gone(child),
                        "the child outlived the driver that was paying for it")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
