"""Reset cards get fresh attempts; earlier runs remain append-only history."""

import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from test_driver import graph_goal
from test_loop import repo_with, task
from test_watchdog import space
from watchdog import check


def failed(here):
    here.attempt("T1", account="work", kind="ok")
    here.event("failed", task="T1", step="gate", why="same gate failure")


class CurrentRunTest(unittest.TestCase):
    def test_old_endings_do_not_quarantine_or_slice_before_new_failures(self):
        here = space()
        here.event("driver_started", pid=6)
        failed(here)
        failed(here)
        self.assertTrue(check(here).spinning)
        self.assertTrue(here.needs_slice("T1"))
        here.event("driver_started", pid=7)
        before = {path: path.read_bytes() for path in here.event_files()}
        self.assertFalse(check(here).spinning)
        self.assertFalse(here.needs_slice("T1"))
        self.assertEqual(before, {path: path.read_bytes() for path in here.event_files()})
        failed(here)
        self.assertFalse(check(here).spinning)
        self.assertFalse(here.needs_slice("T1"))

    def test_two_fresh_identical_endings_still_quarantine_and_slice(self):
        here = space()
        here.event("driver_started", pid=7)
        failed(here)
        failed(here)
        self.assertTrue(check(here).spinning)
        self.assertTrue(here.needs_slice("T1"))

    def test_rotation_does_not_hide_the_run_boundary_or_rewrite_old_parts(self):
        here = space()
        here.max_events_per_file = 2
        failed(here)
        failed(here)
        here.event("driver_started", pid=7)
        failed(here)
        before = {path: path.read_bytes() for path in here.event_files()}
        self.assertFalse(check(here).spinning)
        self.assertFalse(here.needs_slice("T1"))
        self.assertEqual(before, {path: path.read_bytes() for path in here.event_files()})

    def test_driver_attempts_reset_card_twice_before_quarantining(self):
        _, book, here = repo_with(task())
        here.event("driver_started", pid=6)
        failed(here)
        failed(here)
        (here.root / "approved").touch()
        (here.root / "contact").write_text("person@example.test\n")
        before = (here.root / "events.jsonl").read_bytes()
        attempts = []

        def lane(loop, book, here, taking, **kwargs):
            self.assertEqual("todo", book.task("T1")["status"])
            self.assertFalse(check(here).spinning)
            attempts.append(taking[0]["id"])
            failed(here)
            return 1, False

        with mock.patch.object(graph_goal, "run_lanes", side_effect=lane), \
                mock.patch.object(graph_goal, "turn_opens", return_value=None), \
                mock.patch("driver_turn.diagnose", return_value=[]), \
                mock.patch("alert_email.send"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, graph_goal.main(["--workspace", str(here.root), "run",
                                               "--lanes", "1", "--max-tasks", "2"]))
        self.assertEqual(["T1", "T1"], attempts)
        self.assertEqual("quarantined", book.task("T1")["status"])
        self.assertTrue((here.root / "events.jsonl").read_bytes().startswith(before))


if __name__ == "__main__":
    unittest.main()
