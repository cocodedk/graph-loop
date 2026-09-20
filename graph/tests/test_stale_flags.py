"""A FATAL flag standing 15+ minutes is emailed once, high priority — and only
once: the same standing flag never repeats, a returning flag is news again.

Fatal is `notice.fatal`: the supervisor's stand-down, the one thing a person
alone can clear. Until astra's round-3 finding 18 every red flag escalated this
way ("a flag that has stood 15+ minutes emails the owner ONCE"), which
contradicts CLAUDE.md § Code: an ordinary flag is answered by the decision
about its card. Round 4's finding 16 took the disk warning off that list too —
a disk about to fill stands the supervisor DOWN, and its words travel inside
that notice. The rules below are unchanged; what changed is which flags they
are asked about, so both fixtures here are stand-downs. That an ordinary flag
is not emailed at all is asserted in test_only_a_fatal_flag_is_emailed.py.
"""

from __future__ import annotations

import contextlib
import datetime
import io
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import stale_flags
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 8
# the two ways a supervisor stands down, which is all a person is ever mailed
# (notice.fatal): a disk about to fill, in the board's own words, and a dead
# driver. The disk one carries its free space — a number that ticks, which is
# exactly what the dedupe key blanks.
DISK = "  !! the supervisor stood down: DISK NEARLY FULL — 3.1 GB free where the worktrees live"
DOWN = "  !! the supervisor stood down: the driver died five times in a row"


def _age(path: pathlib.Path, minutes: float) -> None:
    then = datetime.datetime.now(datetime.timezone.utc).timestamp() - minutes * 60
    os.utime(path, (then, then))


def _stamp(minutes_ago: float) -> str:
    at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    return at.strftime("%Y-%m-%dT%H:%M:%S%z")


class StaleFlagTest(unittest.TestCase):
    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.check = self.camp / "last-check.txt"
        self.sent = []
        self.real = stale_flags.send
        stale_flags.send = lambda why, flags, important=False: self.sent.append((why, flags, important))
        self.addCleanup(setattr, stale_flags, "send", self.real)

    def tick(self, *lines):
        self.check.write_text("\n".join(lines) + "\n", "utf-8")
        stale_flags.main(str(self.camp), str(self.check))

    def test_a_stale_flag_is_emailed_once_and_marked_important(self):
        old = f"{DISK}   (since {_stamp(20)})"
        fresh = f"{DOWN}   (since {_stamp(1)})"
        self.tick(old, fresh)
        self.assertEqual(1, len(self.sent))                     # the fresh one waits
        why, flags, important = self.sent[0]
        self.assertIn("at least 15 minutes", why)
        self.assertIn("DISK NEARLY FULL", flags)
        self.assertNotIn("died five times", flags)               # only the old one went
        self.assertTrue(important)
        self.tick(old, fresh)
        self.tick(old)
        ticked = old.replace("3.1 GB", "1.2 GB")                # a counter moved, same flag
        self.tick(ticked)
        self.assertEqual(1, len(self.sent))                     # once, not 100 times

    def test_a_mail_failure_is_retried_and_distinct_flags_both_send(self):
        def broken(why, flags, important=False):
            raise OSError("smtp down")
        import stale_flags
        stale_flags.send = broken
        line_a = f"{DISK}   (since {_stamp(20)})"
        line_b = f"{DOWN}   (since {_stamp(20)})"
        with self.assertRaises(OSError):
            self.tick(line_a, line_b)
        stale_flags.send = lambda why, flags, important=False: self.sent.append((why, flags, important))
        self.tick(line_a, line_b)                               # the mail failed: retried
        self.assertEqual(1, len(self.sent))
        self.assertIn("DISK NEARLY FULL", self.sent[0][1])      # both distinct flags sent
        self.assertIn("died five times", self.sent[0][1])
        self.tick(line_a, line_b)
        self.assertEqual(1, len(self.sent))                     # and only once

    def test_a_flag_that_clears_and_returns_is_news_again(self):
        self.tick(f"{DISK}   (since {_stamp(30)})")
        self.tick()                                             # board went green
        self.tick(f"{DISK}   (since {_stamp(16)})")             # back, new first-seen
        self.assertEqual(2, len(self.sent))


class ThresholdTest(unittest.TestCase):
    setUp = StaleFlagTest.setUp
    tick = StaleFlagTest.tick

    def test_the_fifteen_minute_line_is_measured_in_seconds(self):
        self.tick(f"{DISK}   (since {_stamp(14.6)})")           # 14m36s: not yet
        self.assertEqual(0, len(self.sent))
        self.tick(f"{DOWN}   (since {_stamp(15.4)})")           # 15m24s: stale
        self.assertEqual(1, len(self.sent))
        self.assertIn("died five times", self.sent[0][1])
        self.assertNotIn("DISK", self.sent[0][1])


class GreenTickTest(unittest.TestCase):
    def setUp(self):
        StaleFlagTest.setUp(self)

    tick = StaleFlagTest.tick

    def test_a_green_tick_prunes_so_a_same_minute_return_is_news(self):
        line = f"{DISK}   (since {_stamp(20)})"
        self.tick(line)
        self.tick("no red flags")                               # green prunes the record
        self.tick(line)                                         # same stamp, back at once
        self.assertEqual(2, len(self.sent))


class EscalationHoldTest(unittest.TestCase):
    """Someone is already on the board: hold the mail, log why, and leave the
    flag out of the sent-record so it is still news the moment nobody is."""
    setUp = StaleFlagTest.setUp
    tick = StaleFlagTest.tick

    def test_a_fresh_heartbeat_holds_the_escalation(self):
        (self.camp / "WATCHER.heartbeat").write_text("", "utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.tick(f"{DISK}   (since {_stamp(20)})")
        self.assertEqual(0, len(self.sent))
        self.assertIn("escalation held: WATCHER is watching", buf.getvalue())

    def test_a_stale_heartbeat_still_escalates(self):
        hb = self.camp / "WATCHER.heartbeat"
        hb.write_text("", "utf-8")
        _age(hb, 31)
        self.tick(f"{DISK}   (since {_stamp(20)})")
        self.assertEqual(1, len(self.sent))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
