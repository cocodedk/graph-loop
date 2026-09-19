"""Only a flag a person alone can clear becomes an email.

The loop never waits for a person to read or evaluate text (CLAUDE.md § Code):
an ordinary red flag is answered by the decision about its card, and a mail
about it is a handoff to somebody who is not coming. One flag is not that — the
supervisor's stand-down, a loop with nothing running — and `notice.fatal` is
the one reading of which (astra's round-3 finding 18; a routine escalation was
observed in the campaign's own supervisor.log).

A disk about to fill was the second until round 4's finding 16: it is a
warning on the board and a route to nobody, because it STANDS THE SUPERVISOR
DOWN, and the notice that stand-down writes carries the disk words with it.
"""

from __future__ import annotations

import datetime
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import stale_flags
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 3


def stamp(minutes_ago: float) -> str:
    at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    return at.strftime("%Y-%m-%dT%H:%M:%S%z")


class FatalOnlyTest(unittest.TestCase):
    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.check = self.camp / "last-check.txt"
        self.sent: list = []
        real = stale_flags.send
        stale_flags.send = lambda why, flags, important=False: self.sent.append(flags)
        self.addCleanup(setattr, stale_flags, "send", real)

    def tick(self, *lines: str) -> None:
        self.check.write_text("\n".join(lines) + "\n", "utf-8")
        stale_flags.main(str(self.camp), str(self.check))

    def test_an_ordinary_standing_flag_is_never_emailed(self):
        self.tick(f"  !! T26 is stuck   (since {stamp(20)})")
        self.assertEqual([], self.sent, "a routine flag was handed to a person")

    def test_a_disk_warning_reaches_him_only_once_it_stood_the_loop_down(self):
        self.tick(f"  DISK NEARLY FULL — 3.1 GB free   (since {stamp(20)})")
        self.assertEqual([], self.sent, "a warning with the loop still running was mailed")
        self.tick("  !! the supervisor stood down: DISK NEARLY FULL — 3.1 GB free "
                  f"  (since {stamp(20)})")
        self.assertEqual(1, len(self.sent))
        self.assertIn("DISK NEARLY FULL", self.sent[0])     # the words travel with it


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
