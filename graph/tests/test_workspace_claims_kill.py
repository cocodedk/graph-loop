"""`kill_running`'s signal/wait/escalate path, and the identity check that
keeps it off a reused pid. Split from `test_workspace_claims` at the
200-line cap.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import workspace_kill
from test_workspace import fresh
from workspace import Workspace

EXPECTED_TESTS = 6


def _kill_quietly(pgid: int) -> None:
    try:
        os.killpg(pgid, 9)
    except ProcessLookupError:
        pass


def _gone(pid: int) -> bool:
    """True once `pid` is fully gone — not merely a zombie, which still
    answers to signal 0 until its parent (or, once orphaned, init) reaps it."""
    try:
        state = pathlib.Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return True
    return state == "Z"


def _group_dead(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


class TermIgnoringChildTest(unittest.TestCase):
    def test_stop_now_kills_a_term_ignoring_child_too(self):
        # finding 1: a bare SIGTERM is not enough — a TERM-trapping child
        # must still die via finish_kill's bounded wait-then-KILL escalation.
        # The child's sleep (1.5s) outlasts the patched grace period (0.3s)
        # but not the test's wait (2.5s), so a survivor would still show up.
        tmp = pathlib.Path(tempfile.mkdtemp())
        marker, pidfile = tmp / "late", tmp / "child.pid"
        inner = (f"echo $$ > {pidfile}; trap '' TERM; exec </dev/null >/dev/null 2>&1; "
                 f"sleep 1.5; echo late > {marker}")
        driver_script = (
            "import subprocess, time\n"
            f"subprocess.Popen(['bash', '-c', {inner!r}], start_new_session=True)\n"
            "time.sleep(30)\n"
        )
        driver = subprocess.Popen([sys.executable, "-c", driver_script], start_new_session=True)
        self.addCleanup(driver.wait)
        self.addCleanup(_kill_quietly, driver.pid)

        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(pidfile.exists(), "the TERM-ignoring child never started")
        child_pid = int(pidfile.read_text())

        space = fresh()
        space.claim("T1", pid=driver.pid, pgid=driver.pid, account="work", worktree="/tmp/x")
        with unittest.mock.patch("runner.GRACE_SECONDS", 0.3):
            space.kill_running()

        time.sleep(2.5)
        self.assertFalse(marker.exists(), "the TERM-ignoring child outlived stop --now")
        self.assertIsNotNone(driver.poll(), "the driver survived stop --now")
        self.assertTrue(_gone(child_pid), "the TERM-ignoring child survived stop --now")
        self.assertTrue(_group_dead(driver.pid), "the driver's group survived stop --now")
        self.assertTrue(_group_dead(child_pid), "the TERM-ignoring child's group survived stop --now")


class BarrierRaceTest(unittest.TestCase):
    def test_nothing_spawned_during_the_scan_survives(self):
        # finding 2: `workspace_kill._children_of` is patched to snapshot
        # immediately, then sleep 0.5s before returning — long enough that a
        # pre-fix driver (still running through the sleep) keeps spawning
        # children the snapshot missed. Each child lives 2s, past that
        # 0.5s, so a surviving marker means the snapshot missed it, not a
        # late kill. Post-fix the group is frozen (SIGSTOP) before the
        # snapshot is taken, so nothing spawns after it.
        tmp = pathlib.Path(tempfile.mkdtemp())
        markers = tmp / "markers"
        markers.mkdir()
        driver_script = (
            "import itertools, subprocess, time\n"
            "for i in itertools.count():\n"
            f"    subprocess.Popen(['bash', '-c', 'sleep 2; echo done > {markers}/' + str(i)],\n"
            "                      start_new_session=True)\n"
            "    time.sleep(0.1)\n"
        )
        driver = subprocess.Popen([sys.executable, "-c", driver_script], start_new_session=True)
        self.addCleanup(driver.wait)
        self.addCleanup(_kill_quietly, driver.pid)

        time.sleep(0.15)   # the driver has spawned at least one child by now

        space = fresh()
        space.claim("T1", pid=driver.pid, pgid=driver.pid, account="work", worktree="/tmp/x")
        real_children_of = workspace_kill._children_of

        def slow_children_of(pid):
            found = real_children_of(pid)
            time.sleep(0.5)   # meanwhile a still-running (pre-fix) driver keeps spawning
            return found

        with unittest.mock.patch("workspace_kill._children_of", side_effect=slow_children_of), \
             unittest.mock.patch("runner.GRACE_SECONDS", 0.05):
            space.kill_running()

        time.sleep(3)
        self.assertEqual([], sorted(p.name for p in markers.iterdir()),
                          "a child spawned during the scan survived stop --now")


class ParallelLaneKillTest(unittest.TestCase):
    def test_two_claims_on_one_process_are_both_reported_killed(self):
        # finding 1 (this round): parallel lanes can claim the same driver
        # pid/pgid. Before the fix the second claim was checked after the
        # first had already killed the process, read as a reused pid, and
        # came back "mismatched" instead of killed.
        stand_in = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(stand_in.wait)
        self.addCleanup(_kill_quietly, stand_in.pid)

        space = fresh()
        space.claim("T1", pid=stand_in.pid, pgid=stand_in.pid, account="work", worktree="/tmp/x")
        space.claim("T2", pid=stand_in.pid, pgid=stand_in.pid, account="work", worktree="/tmp/y")

        with unittest.mock.patch("workspace_kill.finish_kill",
                                  wraps=workspace_kill.finish_kill) as finish:
            stopped = space.kill_running()

        self.assertEqual({"T1", "T2"}, set(stopped))
        self.assertEqual(1, finish.call_count, "the kill sequence ran more than once for one process")
        self.assertTrue(_group_dead(stand_in.pid), "the shared process survived stop --now")


class UnverifiedClaimTest(unittest.TestCase):
    """Never signal without proof: a changed identity, or an empty one."""

    def _claim_stand_in(self, root, space, task_id, started):
        proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(proc.wait)
        self.addCleanup(_kill_quietly, proc.pid)
        space.claim(task_id, pid=proc.pid, pgid=proc.pid, account="work", worktree="/tmp/x")
        claims = json.loads((root / "claims.json").read_text())
        claims[task_id]["started"] = started
        (root / "claims.json").write_text(json.dumps(claims))
        return proc

    def test_a_reused_pid_is_skipped_and_reported(self):
        root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        space = Workspace(root)
        stand_in = self._claim_stand_in(root, space, "T1", "a-different-boot:999999")

        stopped = space.kill_running()

        self.assertEqual([], stopped)
        self.assertIsNone(stand_in.poll(), "the mismatched claim was signalled")
        self.assertIn("unverified", [row["kind"] for row in space.events()])

    def test_an_empty_recorded_identity_is_skipped_and_reported(self):
        root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        space = Workspace(root)
        stand_in = self._claim_stand_in(root, space, "T1", "")

        stopped = space.kill_running()

        self.assertEqual([], stopped)
        self.assertIsNone(stand_in.poll(), "a claim with no recorded identity was signalled")
        self.assertIn("unverified", [row["kind"] for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
