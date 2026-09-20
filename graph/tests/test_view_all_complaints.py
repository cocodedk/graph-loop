"""The cap on complaints belongs to the screen, never to the alarm.

`--check` (watch.sh --check -> view.red_flags) read the same four rendered
lines the board shows, so a standing old complaint masked every newer one for
ever — the campaign recorded ten at once, queue starvation among them. Every
complaint must also reach the stamps (view_stamps) unchanged, or a flag the
screen happens not to render loses its first-seen time and the 15-minute
email (stale_flags) never counts it as standing.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import view
import view_pulse
from doctor_types import Complaint

EXPECTED_TESTS = 3

FIVE = [Complaint(f"T{n}", f"complaint {n}", "do something") for n in range(1, 6)]


class StubSpace:
    def __init__(self, *a): pass
    def events(self): return []
    def alerts(self): return []


class EveryComplaintReachesTheAlarm(unittest.TestCase):
    def setUp(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        self.camp = pathlib.Path(home.name)
        for patch in (
            unittest.mock.patch.object(view, "Workspace", StubSpace),
            unittest.mock.patch.object(view, "CAMPAIGN", self.camp),
            unittest.mock.patch.object(view_pulse, "CAMPAIGN", self.camp),
            unittest.mock.patch.object(view, "driver_missing", lambda *a: ""),
            unittest.mock.patch.object(view, "_supervisor_last_word", lambda: ([], 0.0)),
            unittest.mock.patch.object(view, "base_measure", lambda *a, **k: ""),
            unittest.mock.patch.object(view, "_driver_start", lambda *a, **k: None),
            unittest.mock.patch.object(view, "health_failures", list),
            # the alarm path passes everything=True; this stub only has to answer
            unittest.mock.patch.object(view, "alerts", lambda everything=False: []),
            unittest.mock.patch("doctor.diagnose", lambda *a, **k: FIVE),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def test_the_fifth_complaint_reaches_the_check_while_the_screen_shows_four(self):
        alarm = view.red_flags()
        screen = view.warnings()
        self.assertEqual(5, len([line for line in alarm if "complaint" in line]))
        self.assertIn("complaint 5", "\n".join(alarm))
        self.assertEqual(4, len([line for line in screen if "complaint" in line]))

    def test_a_complaint_the_screen_does_not_render_is_still_stamped(self):
        view.warnings()
        record = json.loads((self.camp / "flags-seen.json").read_text("utf-8"))
        self.assertEqual(5, len(record["warnings"]))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
