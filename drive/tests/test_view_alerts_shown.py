"""`view.alerts()` leaves the count it displayed behind in `ALERTS.shown`, so
`watch.sh --read` can hand that number straight to `alerts_read` — untouched
by any alert that lands between the showing and the marking.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import threading
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import view
from workspace import Workspace

EXPECTED_TESTS = 5


class AlertsShownTest(unittest.TestCase):
    def setUp(self):
        self.campaign = pathlib.Path(tempfile.mkdtemp())
        patch = unittest.mock.patch.object(view, "CAMPAIGN", self.campaign)
        patch.start()
        self.addCleanup(patch.stop)
        self.space = Workspace(self.campaign)

    def test_the_shown_mark_survives_an_alert_that_lands_after_the_render(self):
        self.space.alert("T1", "first")
        self.space.alert("T1", "second")
        view.alerts()                                     # renders — and marks what it showed
        self.assertEqual("2", (self.campaign / "ALERTS.shown").read_text("utf-8"))
        self.space.alert("T2", "arrived after the render")   # the race
        shown = int((self.campaign / "ALERTS.shown").read_text("utf-8"))
        self.space.alerts_read(shown)
        unread = self.space.alerts()
        self.assertEqual(1, len(unread))
        self.assertIn("arrived after the render", unread[0])

    def test_the_mark_adds_to_what_is_already_read_not_just_this_batch(self):
        (self.campaign / "ALERTS.read").write_text("3", "utf-8")
        for n in range(5):
            self.space.alert("T1", f"alert {n}")
        view.alerts()
        self.assertEqual("5", (self.campaign / "ALERTS.shown").read_text("utf-8"))

    def test_only_what_renders_is_marked_and_the_rest_waits(self):
        for n in range(5):
            self.space.alert("T1", f"alert {n}")
        shown = "\n".join(view.alerts())
        self.assertIn("alert 3", shown)
        self.assertNotIn("alert 4", shown)                # the fifth stays off-screen
        self.assertEqual("4", (self.campaign / "ALERTS.shown").read_text("utf-8"))
        self.space.alerts_read(4)
        unread = self.space.alerts()
        self.assertEqual(1, len(unread))
        self.assertIn("alert 4", unread[0])                # not lost — waiting
        next_render = "\n".join(view.alerts())
        self.assertIn("alert 4", next_render)              # the next render shows it
        self.assertEqual("5", (self.campaign / "ALERTS.shown").read_text("utf-8"))

    def test_an_alert_landing_between_the_snapshot_and_the_mark_is_not_folded_in(self):
        """A real race, not a mock: one thread renders — snapshot, then mark —
        the other appends. Two events force the append to land in the gap
        between them. The mark must stay at what the snapshot saw, not the
        file's count once the appended alert has landed."""
        self.space.alert("T1", "first")
        self.space.alert("T1", "second")
        snapshot_done = threading.Event()
        append_done = threading.Event()
        result: dict = {}
        errors: list = []

        def render():
            try:
                rows, positions = self.space.alerts_snapshot()
                snapshot_done.set()
                append_done.wait(timeout=5)
                # what a render marks: the line it stopped at, plus one
                self.space.alerts_shown(positions[-1] + 1)
                result["rows"], result["position"] = rows, positions[-1] + 1
            except (OSError, ValueError) as error:  # surfaced on the main thread below
                errors.append(error)

        def writer():
            try:
                snapshot_done.wait(timeout=5)
                self.space.alert("T2", "arrived mid-render")
                append_done.set()
            except (OSError, ValueError) as error:
                errors.append(error)

        renderer = threading.Thread(target=render)
        appender = threading.Thread(target=writer)
        renderer.start()
        appender.start()
        renderer.join(timeout=5)
        appender.join(timeout=5)

        self.assertEqual([], errors)
        self.assertEqual(2, result.get("position"))          # the snapshot's count
        self.assertEqual("2", (self.campaign / "ALERTS.shown").read_text("utf-8"))
        self.space.alerts_read(result["position"])
        unread = self.space.alerts()
        self.assertEqual(1, len(unread))
        self.assertIn("arrived mid-render", unread[0])       # not lost, not folded in


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
