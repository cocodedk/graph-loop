"""Three more findings on `kill_running`'s SIGSTOP/verify/finish_kill path:
identity groups verified on their own, a confirmed-gone return before the
function hands control back, and that same confirmed-gone value actually
read on the way out. Split from `test_workspace_claims_kill` at the
200-line cap.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_workspace_claims_kill import _group_dead, _kill_quietly
from workspace import Workspace

EXPECTED_TESTS = 4


class MixedIdentityGroupTest(unittest.TestCase):
    def test_a_stale_claim_does_not_suppress_a_valid_claim_on_the_same_pid(self):
        # finding 1 (this round): grouping by (pid, pgid) alone let whichever
        # claim was seen first decide the verdict for every claim sharing
        # that pid/pgid — a stale `started` could clear a valid claim, or a
        # valid one could wave a stale claim through. T1 keeps its true
        # recorded identity; T2's is overwritten as if left behind by an
        # earlier process at the same pid. Grouping by (pid, pgid, started)
        # puts them in separate identity groups, verified on their own.
        stand_in = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(stand_in.wait)
        self.addCleanup(_kill_quietly, stand_in.pid)

        root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        space = Workspace(root)
        space.claim("T1", pid=stand_in.pid, pgid=stand_in.pid, account="work", worktree="/tmp/x")
        space.claim("T2", pid=stand_in.pid, pgid=stand_in.pid, account="work", worktree="/tmp/y")
        claims = json.loads((root / "claims.json").read_text())
        claims["T2"]["started"] = "a-different-boot:999999"
        (root / "claims.json").write_text(json.dumps(claims))

        stopped = space.kill_running()

        self.assertEqual(["T1"], stopped)
        unverified = [row["tasks"] for row in space.events() if row["kind"] == "unverified"]
        self.assertEqual([["T2"]], unverified)
        self.assertTrue(_group_dead(stand_in.pid), "the valid claim's process survived stop --now")


class SigkillWaitTest(unittest.TestCase):
    def test_a_term_resistant_group_is_gone_when_kill_running_returns(self):
        # finding 2: finish_kill escalated to SIGKILL and returned without
        # confirming the group was actually gone — still a zombie until
        # something reaps it. No sleep here: a zombie still answers to
        # killpg(pgid, 0), so this only passes if kill_running itself waited
        # for the reap before handing control back.
        proc = subprocess.Popen(
            ["bash", "-c", "trap '' TERM; exec </dev/null >/dev/null 2>&1; sleep 60"],
            start_new_session=True)
        self.addCleanup(proc.wait)
        self.addCleanup(_kill_quietly, proc.pid)

        space = Workspace(pathlib.Path(self.enterContext(tempfile.TemporaryDirectory())))
        space.claim("T1", pid=proc.pid, pgid=proc.pid, account="work", worktree="/tmp/x")

        with unittest.mock.patch("runner.GRACE_SECONDS", 0.1):
            stopped = space.kill_running()

        self.assertEqual(["T1"], stopped)
        with self.assertRaises(ProcessLookupError):
            os.killpg(proc.pid, 0)


class UnresolvedGroupTest(unittest.TestCase):
    def test_a_group_still_there_after_the_final_poll_is_recorded_unresolved(self):
        # finding 3: `finish_kill` discarded the result of its own final
        # poll and returned whether a signal was merely sent — so a group
        # still there after SIGKILL was still recorded `killed`. The real
        # process dies normally underneath (no leak); only what the two
        # polls report back is forced to "still there", so a pre-fix
        # `finish_kill` (True regardless) and a post-fix one (the last
        # poll's own answer) disagree on the one thing this checks.
        stand_in = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(stand_in.wait)
        self.addCleanup(_kill_quietly, stand_in.pid)

        root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        space = Workspace(root)
        space.claim("T1", pid=stand_in.pid, pgid=stand_in.pid, account="work", worktree="/tmp/x")

        with unittest.mock.patch("runner.group_gone", side_effect=[False, False]):
            stopped = space.kill_running()

        self.assertEqual([], stopped, "a group the final poll says is still there was reported killed")
        unresolved = [row["tasks"] for row in space.events() if row["kind"] == "unresolved"]
        self.assertEqual([["T1"]], unresolved)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
