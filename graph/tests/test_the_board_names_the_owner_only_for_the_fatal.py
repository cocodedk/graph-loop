"""What the messenger is told to do with a red board.

The message used to end "if only the owner can clear it, say so to them" for every
warning, which is a handoff to a person the loop is not allowed to wait for
(CLAUDE.md § Code, astra's round-3 finding 18). A routine board is the reader's
own to decide, gaps recorded on the card; only a board carrying the fatal
notice or a nearly full disk names him.

Rig from test_alert_watcher.py, the front door of this suite.
"""

from __future__ import annotations

import pathlib
import unittest

from test_alert_watcher import Rig

EXPECTED_TESTS = 7
FATAL = ("  !! the supervisor stood down: the driver died five times in a row, so nothing "
         "is running   (stood down 2026-09-08T10:00:00+0200, supervisor 4242)")


class MessengerBodyTest(Rig):
    def prompt(self, flags: str) -> str:
        self.claude_faithful()
        self.run_alert(flags)
        return (self.camp / "prompt.txt").read_text("utf-8")

    def test_a_routine_board_is_the_readers_own_to_decide(self):
        said = self.prompt("  !! T26 is stuck   (since 2026-09-08T09:00+0200)")
        self.assertNotIn("the owner", said)
        self.assertIn("record", said)       # what it says instead: name the gap

    def test_a_fatal_board_still_names_him(self):
        self.assertIn("the owner", self.prompt(FATAL))


class FallbackMailTest(Rig):
    """And when nobody could be reached at all: the mail is the same rule.

    It used to carry whatever the board said, so an unreachable messenger
    turned every ordinary warning into a mail — the escalation `stale_flags`
    had just stopped making (Codex on the finding-18 brick).
    """
    ROUTINE = "  !! T26 is stuck   (since 2026-09-08T09:00+0200)"

    def unreachable(self, flags: str) -> int:
        self.claude_answers("")                      # nobody answered
        return self.run_alert(flags, email_rc=0)

    def test_a_routine_board_nobody_could_be_told_about_is_not_emailed(self):
        self.assertEqual(1, self.unreachable(self.ROUTINE))
        self.assertFalse((self.camp / "mailed.txt").exists(),
                         "an ordinary warning was mailed to a person")
        self.assertIn("nothing here is a person's to clear", self.log())

    def test_a_mixed_board_mails_the_fatal_line_alone(self):
        self.assertEqual(0, self.unreachable(FATAL + "\n" + self.ROUTINE))
        mailed = (self.camp / "mailed.txt").read_text("utf-8")
        self.assertIn("the supervisor stood down", mailed)
        self.assertNotIn("T26 is stuck", mailed)

    def test_the_mail_does_not_stand_in_for_the_board_the_messenger_owes(self):
        """A mail of the fatal lines is not a delivery of the whole board: the
        ordinary warning beside them still has to reach a session, so the
        messenger's own record stays unwritten (an independent review)."""
        board = FATAL + "\n" + self.ROUTINE
        self.assertEqual(0, self.unreachable(board))          # the mail goes out
        self.claude_faithful()                                # the session is back
        self.assertEqual(0, self.run_alert(board))
        self.assertIn("delivered to WATCHER", self.log())

    def test_a_changed_routine_flag_does_not_re_mail_the_same_fatal_lines(self):
        """The mail's dedupe is the mail's own bytes. Keyed on the whole board,
        T26 becoming T27 sent the identical stand-down mail again."""
        self.assertEqual(0, self.unreachable(FATAL + "\n" + self.ROUTINE))
        self.assertEqual(1, self.unreachable(
            FATAL + "\n" + self.ROUTINE.replace("T26", "T27")))
        self.assertEqual(1, self.log().count("already emailed for this standing state"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
