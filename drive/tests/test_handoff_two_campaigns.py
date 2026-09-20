"""Two campaigns, two stand-ins: neither may touch the other's session.

handoff-standin.sh gave every stand-in the same tmux session name, and replaced any
session under that name whose id it had not recorded — so a second campaign's
live session, working, was killed by the first campaign's next handoff (astra's
round-2 finding 14). The campaign is part of the session name now, so one
campaign never sees the other's session at all.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

DRIVE = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_TESTS = 4

# a fake tmux that keeps one state file PER SESSION NAME, holding the command
# that session was started with — which is what the identity check reads back
FAKE = """#!/bin/bash
sub="$1"; shift
name=""; prev=""
for arg in "$@"; do
  case "$prev" in -t|-s|-pt) name="$arg" ;; esac
  prev="$arg"
done
C="$FAKE_TMUX_STATE/$name"
case "$sub" in
  has-session)  [ -f "$C" ] ;;
  new-session)  printf '%s' "${@: -1}" > "$C" ;;
  list-panes)   [ -f "$C" ] && cat "$C" ;;
  kill-session) rm -f "$C" ;;
  capture-pane) echo settled ;;
  load-buffer|paste-buffer|send-keys) : ;;
  *) exit 1 ;;
esac
"""


class TwoCampaignsTest(unittest.TestCase):
    def setUp(self):
        self.state = pathlib.Path(tempfile.mkdtemp())
        self.stub = pathlib.Path(tempfile.mkdtemp())
        self.first = pathlib.Path(tempfile.mkdtemp())
        self.second = pathlib.Path(tempfile.mkdtemp())
        for temp in (self.state, self.stub, self.first, self.second):
            self.addCleanup(shutil.rmtree, temp, ignore_errors=True)
        fake = self.stub / "tmux"
        fake.write_text(FAKE)
        fake.chmod(0o755)

    def handoff(self, campaign: pathlib.Path) -> subprocess.CompletedProcess:
        env = dict(os.environ, DRIVE_CAMPAIGN=str(campaign),
                   PATH=f"{self.stub}:{os.environ['PATH']}",
                   FAKE_TMUX_STATE=str(self.state), DRIVE_BRANCH="campaign/test")
        return subprocess.run(["bash", str(DRIVE / "handoff-standin.sh")], env=env,
                              check=False, capture_output=True, text=True)

    def test_a_second_campaigns_handoff_leaves_the_first_session_running(self):
        self.assertIn("started", self.handoff(self.first).stdout)
        ours = (self.first / "WATCHER-STANDIN.session").read_text("utf-8")
        self.assertIn("started", self.handoff(self.second).stdout)
        running = [path.read_text("utf-8") for path in self.state.iterdir()]
        self.assertTrue(any(f"--session-id {ours}" in command for command in running),
                        "the first campaign's session was killed by the second's handoff")

    def test_neither_campaign_reports_replacing_the_other(self):
        self.handoff(self.first)
        self.assertNotIn("replacing it", self.handoff(self.second).stdout)

    def test_each_campaign_holds_its_own_named_session(self):
        self.handoff(self.first)
        self.handoff(self.second)
        self.assertEqual(2, len(list(self.state.iterdir())))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
