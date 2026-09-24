"""A handoff never kills a session whose identity it cannot prove.

`ours()` reads the running session's own command line back against the id this
campaign recorded. A failed check flowed straight into `kill-session`, so a
terminal under that name which this campaign never started — a launch whose
identity record was lost, or a person's own session — was killed by the next
tick (astra round 4, finding 13). A mismatch is now a conflict: nothing is
killed, the line is said on stderr and written to the campaign's supervisor.log
as `handoff_conflict`, and the run leaves non-zero.

The rig is test_handoff_owns_what_it_kills.py's, the front door for a handoff
run against a fake tmux.
"""

from __future__ import annotations

import pathlib
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_handoff_owns_what_it_kills import HandoffRig
from test_handoff_two_campaigns import FAKE

EXPECTED_TESTS = 2

STRANGER = "env -u CLAUDE_CONFIG_DIR claude --remote-control WATCHER-STANDIN-abcdef01 " \
           "--session-id 99999999-9999-9999-9999-999999999999 --model claude-opus-5"


class ConflictTest(HandoffRig):
    def test_a_session_this_campaign_never_recorded_is_left_running(self):
        self.tmux(FAKE)
        (self.state / self.session).write_text(STRANGER)   # up, and not ours: no record at all
        done = self.handoff()
        self.assertNotEqual(0, done.returncode)
        self.assertTrue((self.state / self.session).exists(),
                        "a session it could not prove its own was killed")
        self.assertEqual(STRANGER, (self.state / self.session).read_text("utf-8"))
        self.assertFalse((self.camp / "WATCHER-STANDIN.session").exists())   # nothing started
        self.assertIn("handoff_conflict", done.stderr)
        self.assertIn("handoff_conflict",
                      (self.camp / "supervisor.log").read_text("utf-8"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
