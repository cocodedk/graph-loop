"""The screen marks the row it stopped at, never a row it never showed.

A resolved alert leaves a gap between the cursor and the rows the screen
renders, and the mark was worked out by arithmetic that assumed no gaps
(`position_after - len(rows) + shown`). With more than four open and resolved
ones after the fourth, that arithmetic ran past an alert nobody had seen; the
next `watch.sh --read` then confirmed it and hid it for good (Codex on
c5a3027a, finding 8).

The snapshot hands back each row's own line number now, and the screen marks
the last one it displayed, plus one.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import view
from workspace import Workspace

EXPECTED_TESTS = 2


class ShownSkipsNoRowTest(unittest.TestCase):
    def setUp(self):
        self.campaign = pathlib.Path(tempfile.mkdtemp())
        patch = unittest.mock.patch.object(view, "CAMPAIGN", self.campaign)
        patch.start()
        self.addCleanup(patch.stop)
        self.space = Workspace(self.campaign)

    def test_a_resolved_gap_does_not_carry_the_mark_past_an_unshown_alert(self):
        for number in range(5):
            self.space.alert("T1", f"about the card {number}")
        for number in range(4):
            self.space.alert("T9", f"answered {number}")
        self.space.alert("T1", "the last one, still asking")
        self.space.resolve_alerts("T9")            # a decision answered those four

        shown = "\n".join(view.alerts())
        self.assertIn("about the card 3", shown)
        self.assertNotIn("about the card 4", shown)     # the fifth stays off-screen
        self.assertEqual("4", (self.campaign / "ALERTS.shown").read_text("utf-8"))

        self.space.alerts_read(4)
        left = self.space.alerts()
        self.assertEqual(2, len(left))                  # neither is lost
        self.assertIn("about the card 4", "\n".join(left))
        self.assertIn("still asking", "\n".join(left))

    def test_showing_every_row_marks_past_the_last_of_them(self):
        self.space.alert("T9", "answered")
        self.space.alert("T1", "still asking")
        self.space.resolve_alerts("T9")
        view.alerts()
        self.assertEqual("2", (self.campaign / "ALERTS.shown").read_text("utf-8"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
