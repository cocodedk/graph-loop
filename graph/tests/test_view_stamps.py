"""A red flag's `(since …)` stamp holds while the flag stands — its ticking
counters included — and starts over when the flag clears and returns. That is
what lets a watcher skip warnings it already sent without skipping a new one."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from view_stamps import stamped

EXPECTED_TESTS = 9


class StampTest(unittest.TestCase):
    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())

    def stamp(self, lines, section="warnings"):
        return stamped(lines, section, self.camp)

    def test_a_standing_flag_keeps_its_first_seen_stamp(self):
        first = self.stamp(["  !! the driver is gone"])
        again = self.stamp(["  !! the driver is gone", "  !! a second flag"])
        self.assertEqual(first[0], again[0])                    # same stamp, tick after tick
        self.assertIn("(since ", again[1])
        self.assertEqual([], self.stamp([]))                    # nothing red stamps nothing

    def test_a_counter_that_ticks_is_the_same_standing_flag(self):
        first = self.stamp(["  !! nothing has happened for 25 minutes"])
        later = self.stamp(["  !! nothing has happened for 40 minutes"])
        self.assertEqual(first[0].split("(since ")[1], later[0].split("(since ")[1])

    def test_a_decimal_hour_boundary_is_the_same_standing_flag(self):
        first = self.stamp(["  !! quiet for 1.9 hours"])
        later = self.stamp(["  !! quiet for 2.0 hours"])
        self.assertEqual(first[0].split("(since ")[1], later[0].split("(since ")[1])

    def test_a_falling_disk_is_the_same_standing_flag(self):
        first = self.stamp(["  DISK NEARLY FULL — 19.2 GB free (floor 20.0 GB)"])
        later = self.stamp(["  DISK NEARLY FULL — 18.1 GB free (floor 20.0 GB)"])
        self.assertEqual(first[0].split("(since ")[1], later[0].split("(since ")[1])

    def test_a_different_task_id_is_a_different_flag(self):
        import json
        self.stamp(["  !! T25 is stuck"])
        record = self.camp / "flags-seen.json"
        aged = json.loads(record.read_text())
        aged["warnings"]["!! T25 is stuck"] = "2026-01-01T00:00+0000"
        record.write_text(json.dumps(aged))
        lines = self.stamp(["  !! T25 is stuck", "  !! T26 is stuck"])
        self.assertIn("2026-01-01", lines[0])                   # T25 keeps its age
        self.assertNotIn("2026-01-01", lines[1])                # T26 is new, not T25's heir

    def test_a_flag_that_clears_and_returns_begins_again(self):
        record = self.camp / "flags-seen.json"
        self.stamp(["  !! red"])
        record.write_text(json.dumps({"warnings": {"!! red": "2026-01-01T00:00+0000"}}))
        aged = self.stamp(["  !! red"])[0]
        self.assertIn("2026-01-01", aged)                       # the record is what stamps
        self.stamp([])                                          # the flag cleared
        back = self.stamp(["  !! red"])[0]
        self.assertNotIn("2026-01-01", back)                    # and began again

    def test_concurrent_sections_never_lose_each_other(self):
        # the screen loop and the supervisor's ticker write the same record
        def hammer(section):
            for _ in range(30):
                stamped([f"  !! {section} flag"], section, self.camp)
        threads = [threading.Thread(target=hammer, args=(s,)) for s in ("health", "alerts")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        record = json.loads((self.camp / "flags-seen.json").read_text())
        self.assertIn("health", record)
        self.assertIn("alerts", record)


class ClearedAlertTest(unittest.TestCase):
    def test_a_cleared_alert_that_returns_begins_again(self):
        import json
        import unittest.mock

        import view

        camp = pathlib.Path(tempfile.mkdtemp())

        class StubSpace:
            rows: tuple = ()
            def __init__(self, *a): pass
            def alerts(self): return StubSpace.rows
            def alerts_snapshot(self): return StubSpace.rows, list(range(len(StubSpace.rows)))
            def alerts_shown(self, *a): pass

        with unittest.mock.patch.object(view, "CAMPAIGN", camp), \
             unittest.mock.patch.object(view, "Workspace", StubSpace):
            StubSpace.rows = ("a task needs a person",)
            view.alerts()
            record = camp / "flags-seen.json"
            data = json.loads(record.read_text())
            data["alerts"] = {k: "2026-01-01T00:00+0000" for k in data["alerts"]}
            record.write_text(json.dumps(data))
            self.assertIn("2026-01-01", view.alerts()[1])       # standing keeps its age
            StubSpace.rows = ()
            self.assertEqual([], view.alerts())                 # cleared — and recorded so
            StubSpace.rows = ("a task needs a person",)
            self.assertNotIn("2026-01-01", view.alerts()[1])    # returned: a new age


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
