"""WATCHER-STANDIN handoff and its consequences, split out of test_alert_watcher.py
at the 200-line fixpoint (CLAUDE.md) — the old file stays the front door for
Rig, record_for and age, which this file imports rather than redeclares.
Two things live here: alert-watcher.sh's own retry-on-launch logic (proven
without ever touching a real tmux), and the email's own dedupe record, which
must not re-fire every tick just because the messenger keeps retrying."""

from __future__ import annotations

import pathlib
import unittest

from test_alert_watcher import Rig, age, record_for

EXPECTED_TESTS = 5


class HandoffRetryTest(Rig):
    """alert-watcher.sh's own retry-on-handoff logic: handoff-standin.sh is
    swapped for a bare-exit stub via HANDOFF_CAW, the one seam
    alert-watcher.sh exposes for it — tmux/screen are also faked here so
    this suite can never start a real session even if that seam is bypassed."""

    def setUp(self):
        # Rig.setUp(self), not super().setUp(): this method is also aliased
        # onto EmailDedupeTest below, a sibling under Rig rather than a
        # subclass of this one, and implicit super() resolves against the
        # class it was DEFINED in — it would reject that instance.
        Rig.setUp(self)
        for tool in ("tmux", "screen"):
            fake = self.stub / tool
            fake.write_text('#!/bin/bash\n[ "$1" = capture-pane ] && { echo x; exit 0; }\nexit 1\n')
            fake.chmod(0o755)
        hb = self.camp / "WATCHER.heartbeat"
        hb.write_text("", "utf-8")
        age(hb, 31)                                          # stale -> targets WATCHER-STANDIN
        # a FATAL flag: only those are ever mailed, so only those can
        # exercise the email's own dedupe record (lib/notice.py) — which since
        # round-4 finding 16 is the supervisor's stand-down alone, the disk
        # words inside it
        self.line = ("  !! the supervisor stood down: DISK NEARLY FULL — 3.1 GB free"
                     "   (since 2026-08-31T10:00+0200)")
        self.claude_answers(record_for(self.line, success=False))   # never proven

    def stub_handoff(self, rc: int) -> dict:
        path = self.stub / "handoff-standin.sh"
        path.write_text(f"#!/bin/bash\nexit {rc}\n")
        path.chmod(0o755)
        return {"HANDOFF_CAW": str(path)}

    def test_a_launched_stand_in_gets_the_send_retried(self):
        self.run_alert(self.line, extra_env=self.stub_handoff(0))
        self.assertEqual(1, len(list(self.camp.glob("messenger-*-retry.jsonl"))))

    def test_a_handoff_that_never_started_skips_the_retry(self):
        self.run_alert(self.line, extra_env=self.stub_handoff(3))
        self.assertEqual(0, len(list(self.camp.glob("messenger-*-retry.jsonl"))))
        self.assertIn("WARNING", self.log())


class EmailDedupeTest(Rig):
    """The email has its own dedupe record, independent of the messenger's:
    only a proven send writes watcher-alert.last, and the mail writes
    email.last from its own fatal payload, whichever target was being tried —
    an unreachable stand-in must not re-email the same standing state for
    ever."""
    setUp = HandoffRetryTest.setUp
    stub_handoff = HandoffRetryTest.stub_handoff

    def test_an_unreachable_stand_in_emails_once_across_two_ticks(self):
        env = self.stub_handoff(3)                           # never starts -> no retry
        self.run_alert(self.line, email_rc=0, extra_env=env)
        self.run_alert(self.line, email_rc=0, extra_env=env)
        self.assertEqual(2, len(list(self.camp.glob("messenger-*.jsonl"))))   # one send per tick
        self.assertEqual(1, self.log().count("already emailed for this standing state"))

    def test_a_target_switch_with_unchanged_flags_does_not_email_twice(self):
        # "the same red" for email purposes is the flags alone: a primary ->
        # stand-in switch must not re-email just because the target changed.
        hb = self.camp / "WATCHER.heartbeat"
        hb.write_text("", "utf-8")                            # fresh -> tick 1 targets WATCHER
        self.run_alert(self.line, email_rc=0)
        age(hb, 31)                                           # stale -> tick 2 targets WATCHER-STANDIN
        self.run_alert(self.line, email_rc=0, extra_env=self.stub_handoff(3))
        self.assertEqual(1, self.log().count("already emailed for this standing state"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
