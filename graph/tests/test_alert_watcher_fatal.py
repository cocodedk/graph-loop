"""A fatal stand-down stops standing only when a delivery is proven.

supervisor.sh leaves its last words in `stand-down.txt` when the driver has
died five times, and the messenger's "retrying next tick" promised a tick that
died with the supervisor (astra's round-2 finding 13). The file now outlives
the process that wrote it, every `--check` carries it (view_pulse), and this is
the one place it is cleared — where the script already decides somebody was
told — and only by a delivery that actually carried it: Codex found that
delivering an older, unrelated board deleted the pending notice unsent, and
that the mail which did go out to the stand-in left it marked undelivered.
Rig, claude_faithful, age and record_for come from test_alert_watcher.py, the
front door of this rig.
"""

from __future__ import annotations

import pathlib
import unittest

from test_alert_watcher import Rig, age, record_for

EXPECTED_TESTS = 7

# as supervisor.sh writes it: the run that stood down is part of the words, or
# the next stand-down says exactly the same thing
FATAL = ("  !! the supervisor stood down: the driver died five times in a row, so nothing "
         "is running   (stood down 2026-09-08T10:00:00+0200, supervisor 4242)")


class FatalNoticeTest(Rig):
    def test_only_a_proven_delivery_takes_the_stand_down_off_the_board(self):
        standing = self.camp / "stand-down.txt"
        standing.write_text(FATAL + "\n", "utf-8")
        self.claude_answers("")                       # nobody answered: it still stands
        self.assertEqual(1, self.run_alert(FATAL))
        self.assertTrue(standing.exists())
        self.claude_faithful()                        # told, and proven
        self.assertEqual(0, self.run_alert(FATAL))
        self.assertFalse(standing.exists())

    def test_delivering_an_unrelated_board_leaves_the_notice_standing(self):
        standing = self.camp / "stand-down.txt"
        standing.write_text(FATAL + "\n", "utf-8")
        self.claude_faithful()
        self.assertEqual(0, self.run_alert("  !! T9 is stuck   (since 2026-09-08T09:00+0200)"))
        self.assertTrue(standing.exists(), "a delivery that never carried it took it away")

    def test_the_board_that_carried_the_notice_clears_it(self):
        # what --check really sends: every word of the notice, with the board's
        # own age after them
        standing = self.camp / "stand-down.txt"
        standing.write_text(FATAL + "\n", "utf-8")
        board = FATAL + "   (since 2026-09-08T10:31:00+0200)"
        self.claude_faithful()
        self.assertEqual(0, self.run_alert("  !! T9 is stuck   (since 2026-09-08T09:00+0200)\n"
                                           + board))
        self.assertFalse(standing.exists())


class FallbackEmailTest(Rig):
    """An email is a delivery too. The stand-in was unreachable, so the
    messenger's own dedupe record stays unwritten and it is tried again next
    tick — but the owner has the words in their mail, so the notice stops standing."""

    def setUp(self):
        Rig.setUp(self)
        hb = self.camp / "WATCHER.heartbeat"
        hb.write_text("", "utf-8")
        age(hb, 31)                                     # stale -> targets WATCHER-STANDIN
        self.claude_answers(record_for(FATAL, success=False))     # never proven
        stub = self.stub / "handoff-standin.sh"
        stub.write_text("#!/bin/bash\nexit 3\n")       # never starts -> no retry
        stub.chmod(0o755)
        self.handoff = {"HANDOFF_CAW": str(stub)}

    def test_the_mail_that_went_out_clears_the_notice_and_keeps_the_retry(self):
        standing = self.camp / "stand-down.txt"
        standing.write_text(FATAL + "\n", "utf-8")
        self.run_alert(FATAL, email_rc=0, extra_env=self.handoff)
        self.assertFalse(standing.exists(), "the mail went out and it still stands")
        self.assertFalse((self.camp / "watcher-alert.last").exists())   # the retry is kept


class MutableCheckTest(Rig):
    """What goes out is what this run read.

    The messenger stub rewriting the check file stands in for a writer outside
    this run — a person running `watch.sh --check` into the same path while a
    messenger call takes five minutes; the supervisor's own tick waits for this
    script and is never that writer. However it happens, the file the email
    re-read had moved under it: the mail carried one board while the clearing
    compared another (Codex on the finding-13 brick). One snapshot now serves
    the prompt, the mail and the comparison."""

    def test_the_mail_carries_the_board_the_clearing_compared(self):
        standing = self.camp / "stand-down.txt"
        standing.write_text(FATAL + "\n", "utf-8")
        # the messenger fails — and while it runs, something outside this run
        # replaces the check file, as a person re-running the board would
        (self.stub / "claude").write_text(
            "#!/bin/bash\n"
            f"cat > {self.camp}/prompt.txt\n"
            f"printf '%s\\n' '  !! T9 is stuck   (since 2026-09-08T09:00+0200)' > {self.check}\n"
            "exit 1\n")
        (self.stub / "claude").chmod(0o755)
        self.run_alert(FATAL + "   (since 2026-09-08T10:31:00+0200)", email_rc=0)
        # the rewrite really happened, or this test proves nothing about it
        self.assertIn("T9 is stuck", self.check.read_text("utf-8"))
        mailed = (self.camp / "mailed.txt").read_text("utf-8")
        self.assertIn("the supervisor stood down", mailed)      # what was read went out
        self.assertNotIn("T9 is stuck", mailed)                 # not what replaced it
        self.assertFalse(standing.exists())                     # and it cleared the notice


class NoPayloadTest(Rig):
    """A snapshot it could not write is not a payload.

    The write was never checked, so a run that could make no snapshot mailed an
    empty body, took the fatal notice off the board and recorded the flags as
    delivered (Codex on the finding-13 brick). Nothing goes out now."""

    def test_a_snapshot_it_cannot_write_sends_nothing(self):
        standing = self.camp / "stand-down.txt"
        standing.write_text(FATAL + "\n", "utf-8")
        self.claude_faithful()                                  # would deliver, if reached
        rc = self.run_alert(FATAL, email_rc=0,
                            extra_env={"TMPDIR": str(self.camp / "nowhere")})
        self.assertTrue(standing.exists(), "the notice went with a payload nobody could read")
        self.assertFalse((self.camp / "watcher-alert.last").exists())   # nothing recorded
        self.assertFalse((self.camp / "email.last").exists())
        self.assertEqual([], list(self.camp.glob("messenger-*.jsonl")))  # nothing sent
        self.assertFalse((self.camp / "mailed.txt").exists())            # nothing mailed
        self.assertEqual(1, rc)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
