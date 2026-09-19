"""What "already up" is allowed to mean for the stand-in.

handoff-standin.sh answered "already up" for any tmux session under the name, so
a terminal that was not our relay — or ours, hung — stopped the handoff and
the very same tick failed to deliver again (supervisor.log, 2026-09-03
20:53). Up now means the session was started with the id we recorded AND
that id has answered recently (heartbeat.sh touches WATCHER-STANDIN.heartbeat
only for the id in WATCHER-STANDIN.session).

Ours and silent is replaced. A session we cannot prove ours is NOT: round 3
replaced that too, and astra's round-4 finding 13 called it what it is —
killing somebody else's live session. It is left running and reported
(test_a_handoff_leaves_a_session_it_cannot_prove_ours.py), so the 2026-09-03
delivery failure is now a named conflict instead of a silent kill.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_alert_watcher import age

DRIVE = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_TESTS = 5

OURS = "11111111-1111-1111-1111-111111111111"
STRANGER = "99999999-9999-9999-9999-999999999999"

# a stateful fake tmux that remembers the command its session was started
# with, which is what the identity check reads back
FAKE = """#!/bin/bash
C="$FAKE_TMUX_STATE/cmd"
case "$1" in
  has-session)  [ -f "$C" ] ;;
  new-session)  printf '%s' "${@: -1}" > "$C" ;;
  list-panes)   [ -f "$C" ] && cat "$C" ;;
  kill-session) rm -f "$C" ;;
  capture-pane) echo settled ;;
  load-buffer|paste-buffer|send-keys) : ;;
  *) exit 1 ;;
esac
"""


class AlreadyUpTest(unittest.TestCase):
    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.stub = pathlib.Path(tempfile.mkdtemp())
        self.state = pathlib.Path(tempfile.mkdtemp())
        for temp in (self.camp, self.stub, self.state):
            self.addCleanup(shutil.rmtree, temp, ignore_errors=True)
        fake = self.stub / "tmux"
        fake.write_text(FAKE)
        fake.chmod(0o755)

    def running(self, session_id: str) -> None:
        """A session is up under the name, started with this id."""
        (self.state / "cmd").write_text(
            f"env -u CLAUDE_CONFIG_DIR claude --remote-control WATCHER-STANDIN-x "
            f"--session-id {session_id} --model claude-opus-5 --effort high", "utf-8")

    def recorded(self, session_id: str, heartbeat_minutes: int | None) -> None:
        (self.camp / "WATCHER-STANDIN.session").write_text(session_id, "utf-8")
        if heartbeat_minutes is not None:
            beat = self.camp / "WATCHER-STANDIN.heartbeat"
            beat.write_text("", "utf-8")
            age(beat, heartbeat_minutes)

    def run_handoff(self) -> subprocess.CompletedProcess:
        env = dict(os.environ, DRIVE_CAMPAIGN=str(self.camp),
                   PATH=f"{self.stub}:{os.environ['PATH']}",
                   FAKE_TMUX_STATE=str(self.state), DRIVE_BRANCH="campaign/test")
        return subprocess.run(["bash", str(DRIVE / "handoff-standin.sh")], env=env,
                              check=False, capture_output=True, text=True)

    def test_a_session_started_under_another_id_is_not_our_stand_in(self):
        self.running(STRANGER)
        self.recorded(OURS, heartbeat_minutes=0)      # fresh: identity alone decides here
        result = self.run_handoff()
        self.assertNotIn("already up", result.stdout)
        # and not replaced either: it is not ours to kill (round-4 finding 13)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(STRANGER, (self.state / "cmd").read_text("utf-8"))
        self.assertEqual(OURS, (self.camp / "WATCHER-STANDIN.session").read_text("utf-8"))

    def test_our_own_session_that_has_not_answered_is_not_up(self):
        self.running(OURS)
        self.recorded(OURS, heartbeat_minutes=31)     # stale: nobody is answering in there
        result = self.run_handoff()
        self.assertNotIn("already up", result.stdout)
        self.assertNotEqual(OURS, (self.camp / "WATCHER-STANDIN.session").read_text("utf-8"))

    def test_a_replacement_never_inherits_the_beat_of_the_session_it_replaced(self):
        self.running(OURS)
        self.recorded(OURS, heartbeat_minutes=31)  # ours, silent: this one IS replaced
        self.assertIn("started", self.run_handoff().stdout)     # replaced, ours recorded
        second = self.run_handoff()
        self.assertNotIn("already up", second.stdout)           # it has not answered yet

    def test_our_own_session_answering_now_is_already_up(self):
        self.running(OURS)
        self.recorded(OURS, heartbeat_minutes=1)
        result = self.run_handoff()
        self.assertIn("already up", result.stdout)
        self.assertEqual(0, result.returncode)
        self.assertEqual(OURS, (self.camp / "WATCHER-STANDIN.session").read_text("utf-8"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
