"""The cap on alerts belongs to the screen, never to the alarm.

`--check` (watch.sh --check -> view.red_flags) read the same four rendered rows
the board shows, so a fifth thing asking for a person never got a first-seen
time of its own and never reached the 15-minute email (stale_flags) — astra's
round-2 finding 16, the same shape as the complaints cap fixed in finding 18.
Acknowledgement stays with the screen: `ALERTS.shown` is what a render
displayed, and the alarm displays to nobody.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import view
from workspace import Workspace

EXPECTED_TESTS = 4


class EveryAlertReachesTheAlarm(unittest.TestCase):
    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.camp, ignore_errors=True)
        for patch in (
            unittest.mock.patch.object(view, "CAMPAIGN", self.camp),
            unittest.mock.patch.object(view, "health_failures", list),
            unittest.mock.patch.object(view, "warnings", lambda everything=False: []),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        space = Workspace(self.camp)
        for n in range(5):
            space.alert("T1", f"alert {n}")

    def test_the_fifth_alert_reaches_the_check_while_the_screen_shows_four(self):
        alarm = view.red_flags()
        self.assertEqual(5, len([line for line in alarm if "alert " in line]))
        self.assertIn("alert 4", "\n".join(alarm))
        self.assertEqual(4, len([line for line in view.alerts() if "alert " in line]))

    def test_an_alert_the_screen_does_not_render_is_still_stamped(self):
        view.alerts()
        record = json.loads((self.camp / "flags-seen.json").read_text("utf-8"))
        self.assertEqual(5, len(record["alerts"]))

    def test_the_alarm_marks_nothing_shown(self):
        view.red_flags()
        self.assertFalse((self.camp / "ALERTS.shown").exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
