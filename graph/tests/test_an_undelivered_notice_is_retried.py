"""A stand-down nobody could be told about is retried by the supervisor itself.

The supervisor handed its last words to a messenger that failed, logged
"retrying next tick", and exited — killing the ticker that would have retried.
The notice survived on disk, but nothing tried again until a person started
another supervisor, so two channels could come back and nobody would notice
(astra's round-3 finding 16, after round-2 finding 13 made the notice durable).

It now stays alive in notice-only mode: no driver is started, every turn of the
wait retries the standing notice, and it leaves when a delivery is proved or a
stop is asked. `run_supervisor` comes from test_supervisor_stand_down.py, the
front door of this rig.
"""

from __future__ import annotations

import pathlib
import shutil
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_supervisor_stand_down import run_supervisor

EXPECTED_TESTS = 4


class RetryUntilDeliveredTest(unittest.TestCase):
    def test_a_channel_that_comes_back_later_still_gets_the_notice(self):
        # the mail is refused once and goes out on the second attempt — which
        # only ever happens if the supervisor is still there to make it
        log, code, camp = run_supervisor(self, run_exit=75, email_ok_after=2)
        self.assertFalse((camp / "stand-down.txt").exists(),
                         "the notice was never delivered: nothing retried it")
        self.assertGreaterEqual(log.count("alert-watcher"), 2)
        self.assertEqual(5, log.count("starting the driver"))   # no driver in notice mode
        self.assertEqual(1, code)

    def test_the_stand_down_is_the_logs_last_word(self):
        """What the board reads of this log is its last line
        (`view_health.driver_missing`), and it must not end mid-retry."""
        log, _code, _camp = run_supervisor(self, run_exit=75, email_ok_after=2)
        self.assertIn("five immediate failures: standing down for a person",
                      log.strip().splitlines()[-1])


class DeliveredWhileWaitingTest(unittest.TestCase):
    """The ticker carries the same notice to the same messenger, so it can be
    delivered and taken off the board while this waits — and then there is
    nothing to retry (Codex on the finding-16 brick)."""

    def test_a_notice_delivered_while_it_waits_is_not_alerted_again(self):
        camp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, camp, ignore_errors=True)
        log, code, _ = run_supervisor(
            self, run_exit=75, camp=camp,               # the ticker, during the wait
            sleep_hook=f'[ "$1" = "600" ] && rm -f {camp}/stand-down.txt\n')
        self.assertEqual(1, code)
        self.assertFalse((camp / "stand-down.txt").exists())
        self.assertEqual("1\n", (camp / "messenger.count").read_text("utf-8"),
                         "an alert with nothing in it was sent after the delivery")
        self.assertIn("five immediate failures", log.strip().splitlines()[-1])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
