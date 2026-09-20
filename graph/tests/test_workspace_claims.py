"""A claim is alive by its claimant's identity — pid, boot and start tick —
never by a process group the supervisor shares. Split from `test_workspace`
at the 200-line cap."""

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
from test_workspace import fresh
from workspace import Workspace
from workspace_claims import _started

EXPECTED_TESTS = 11


def _gone(pid: int) -> bool:
    """True once `pid` is fully gone — not merely a zombie, which still
    answers to signal 0 until its parent (or, once orphaned, init) reaps it."""
    try:
        state = pathlib.Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return True
    return state == "Z"


class StaleClaimTest(unittest.TestCase):
    def test_a_claim_whose_process_is_gone_is_not_counted_as_running(self):
        # A killed driver leaves its claim behind; the next run must not think a
        # task is still in flight and refuse to start it (seen live, 2026-08-28).
        space = fresh()
        space.claim("T1", pgid=999_999, account="work", worktree="/tmp/x")
        self.assertEqual({}, space.running())
        self.assertEqual(1, len([r for r in space.events() if r["kind"] == "abandoned"]))

    def test_a_claim_whose_pid_is_gone_is_abandoned_even_while_its_group_lives(self):
        # The driver shares its process group with the supervisor: a killed
        # driver left a claim the living supervisor kept "alive" for hours.
        space = Workspace(pathlib.Path(self.enterContext(tempfile.TemporaryDirectory())))
        child = subprocess.Popen(["sleep", "60"])          # a live claimant in THIS group
        space.claim("T1", pid=child.pid, pgid=os.getpgid(0), account="work", worktree="/tmp/x")
        self.assertIn("T1", space.running())
        child.kill(); child.wait()                          # the claimant dies, the group lives on
        self.assertEqual({}, space.running())
        self.assertEqual("abandoned", space.events()[-1]["kind"])

    def test_a_claim_of_a_living_pid_is_still_running(self):
        space = Workspace(pathlib.Path(self.enterContext(tempfile.TemporaryDirectory())))
        space.claim("T1", pid=os.getpid(), pgid=999_999, account="work", worktree="/tmp/x")
        self.assertEqual(os.getpid(), space.running()["T1"]["pid"])

    def test_a_reused_pid_does_not_keep_a_dead_claim_alive(self):
        root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        space = Workspace(root)
        space.claim("T1", pid=os.getpid(), pgid=os.getpgid(0), account="work", worktree="/tmp/x")
        rows = json.loads((root / "claims.json").read_text())
        rows["T1"]["started"] = "an-earlier-boot:" + rows["T1"]["started"].split(":")[1]   # same tick, other boot
        (root / "claims.json").write_text(json.dumps(rows))
        self.assertEqual({}, space.running())

    def test_an_unreadable_proc_is_doubt_and_keeps_the_claim(self):
        space = Workspace(pathlib.Path(self.enterContext(tempfile.TemporaryDirectory())))
        space.claim("T1", pid=os.getpid(), pgid=os.getpgid(0), account="work", worktree="/tmp/x")
        with unittest.mock.patch("workspace_claims._started", return_value=None):
            self.assertIn("T1", space.running())

    def test_a_machine_without_a_boot_id_is_doubt_not_death(self):
        space = fresh()
        space.claim("T1", pid=os.getpid(), pgid=os.getpgid(0), account="work", worktree="/tmp/x")
        with unittest.mock.patch("workspace_claims._boot", return_value=None):
            self.assertIn("T1", space.running())

    def test_a_claim_made_in_doubt_lives_by_its_pid_alone(self):
        space = fresh()
        with unittest.mock.patch("workspace_claims._started", return_value=None):
            space.claim("T1", pid=os.getpid(), pgid=999_999, account="work", worktree="/tmp/x")
            space.claim("T2", pid=999_999, pgid=999_999, account="work", worktree="/tmp/y")
        self.assertEqual(["T1"], sorted(space.running()))   # the later, clear read keeps T1 and drops T2

    def test_a_claim_of_a_living_process_is_still_running(self):
        space = fresh()
        space.claim("T1", pgid=os.getpgid(0), account="work", worktree="/tmp/x")
        self.assertEqual({"T1"}, set(space.running()))


class FreshClaimTest(unittest.TestCase):
    def test_a_fresh_claim_survives_the_sweep_of_a_dead_one(self):
        space = fresh()
        space.claim("T1", pid=999_999, pgid=999_999, account="work", worktree="/tmp/dead")
        rows = json.loads((space.root / "claims.json").read_text())
        rows["T1"] = {**rows["T1"], "pid": os.getpid(), "started": _started(os.getpid()),
                      "worktree": "/tmp/fresh"}       # a lane re-claimed it meanwhile
        (space.root / "claims.json").write_text(json.dumps(rows))
        self.assertIn("T1", space.running())          # the sweep must not drop it


class StopNowTest(unittest.TestCase):
    def test_stop_now_kills_a_child_detached_into_its_own_session(self):
        # runner.run's start_new_session=True gives a gate/model child its own
        # process group, never the one recorded on the claim — the driver's
        # own. stop --now runs as a fresh process reading claims.json from
        # disk, so nothing but that file and /proc says which child to chase.
        tmp = pathlib.Path(tempfile.mkdtemp())
        marker, pidfile = tmp / "late", tmp / "child.pid"
        inner = f"echo $$ > {pidfile}; sleep 2; echo late > {marker}"
        driver_script = (
            "import subprocess, time\n"
            f"subprocess.Popen(['bash', '-c', {inner!r}], start_new_session=True)\n"
            "time.sleep(30)\n"
        )
        driver = subprocess.Popen([sys.executable, "-c", driver_script], start_new_session=True)

        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(pidfile.exists(), "the detached child never started")
        child_pid = int(pidfile.read_text())

        space = fresh()
        # A session leader's own process group is its own pid — the same
        # thing turn.py records for a real driver via os.getpgid(0).
        space.claim("T1", pid=driver.pid, pgid=driver.pid, account="work", worktree="/tmp/x")
        space.kill_running()

        time.sleep(3)
        self.assertFalse(marker.exists(), "the detached child outlived stop --now")
        self.assertIsNotNone(driver.poll(), "the driver survived stop --now")
        self.assertTrue(_gone(child_pid), "the detached child survived stop --now")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
