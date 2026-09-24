"""`alerts_read` marks what the reader actually showed, not whatever is on
file at the moment it is called: an alert that arrives between the showing
and the marking must stay unread, because nobody has seen it yet.

Both `alerts_read` and `alerts_shown` (the candidate mark a render leaves
before `--read` confirms it) share the same rule: monotonic, and bounded to
`0..len(ALERTS.txt rows)` — a mark cannot claim an alert that was never
written.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from workspace import Workspace

EXPECTED_TESTS = 5


def fresh() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="backlog.yaml")


class AlertsReadRaceTest(unittest.TestCase):
    def test_an_alert_that_arrives_after_the_shown_count_stays_unread(self):
        space = fresh()
        space.alert("T1", "first")
        space.alert("T1", "second")
        shown = len(space.alerts())             # the reader displayed these two
        self.assertEqual(2, shown)
        space.alert("T2", "arrived after the reader looked")   # the race
        space.alerts_read(shown)                 # marks only what was shown
        unread = space.alerts()
        self.assertEqual(1, len(unread))
        self.assertIn("arrived after the reader looked", unread[0])


class AlertsReadMonotonicTest(unittest.TestCase):
    def test_a_delayed_older_mark_never_rewinds_a_newer_one(self):
        space = fresh()
        for n in range(7):
            space.alert("T1", f"alert {n}")
        space.alerts_read(7)
        space.alerts_read(5)          # a delayed mark, arriving late
        self.assertEqual("7", (space.root / "ALERTS.read").read_text("utf-8"))

    def test_a_mark_beyond_the_row_count_is_rejected(self):
        space = fresh()
        for n in range(7):
            space.alert("T1", f"alert {n}")
        with self.assertRaises(ValueError):
            space.alerts_read(8)


class AlertsShownMonotonicTest(unittest.TestCase):
    def test_a_delayed_older_mark_never_rewinds_a_newer_one(self):
        space = fresh()
        for n in range(7):
            space.alert("T1", f"alert {n}")
        space.alerts_shown(7)
        space.alerts_shown(5)          # a delayed render, arriving late
        self.assertEqual("7", (space.root / "ALERTS.shown").read_text("utf-8"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
