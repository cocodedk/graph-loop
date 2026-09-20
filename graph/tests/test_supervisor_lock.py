"""Lock contention: a second supervisor started against the same campaign
must never win the flock, and its "already holds" message must never land in
supervisor.log — that log's last line is the board's only read of the
driver's state (view_health.driver_missing), so the lock message standing in
for it once falsely announced a missing driver during a valid backoff
(independent review, commit ef64ddbc)."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

GRAPH = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_TESTS = 2


def _stub_env(camp: pathlib.Path, stub: pathlib.Path) -> dict:
    """A driver stub that just sleeps 2s (standing in for a live driver) so
    the first supervisor holds the lock for the whole test, plus a report
    stub — same shape as the neighbouring stand-down test's stub."""
    stub.mkdir()
    real = shutil.which("python3")
    (stub / "python3").write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        '  *"graph-goal.py run"*) sleep 2; exit 0 ;;\n'
        '  *"graph-goal.py report"*) echo report ;;\n'
        f'  *) exec "{real}" "$@" ;;\n'
        "esac\n")
    (stub / "python3").chmod(0o755)
    return dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}", GRAPH_CAMPAIGN=str(camp))


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=5)


class LockContentionTest(unittest.TestCase):
    def test_second_supervisors_lock_message_stays_off_the_log(self):
        camp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, camp, ignore_errors=True)
        env = _stub_env(camp, camp / "bin")
        log = camp / "supervisor.log"

        first = subprocess.Popen(["bash", str(GRAPH / "supervisor.sh")], env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(_terminate, first)
        deadline = time.time() + 3
        while time.time() < deadline:
            if log.exists() and "starting the driver" in log.read_text("utf-8"):
                break
            time.sleep(0.05)
        else:
            self.fail("first supervisor never logged starting the driver")

        started = time.time()
        second = subprocess.run(["bash", str(GRAPH / "supervisor.sh")], env=env, check=False,
                                capture_output=True, text=True, timeout=10)
        elapsed = time.time() - started

        self.assertEqual(0, second.returncode, second.stderr)
        self.assertLess(elapsed, 1.0, "flock -n must never block")
        self.assertIn("already holds", second.stderr)

        last_line = log.read_text("utf-8").strip().splitlines()[-1]
        self.assertNotIn("already holds", last_line)          # the first supervisor's own word
        self.assertIn("starting the driver", last_line)

        first.wait(timeout=5)                                  # rc=0 stub: finishes and stands down


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
