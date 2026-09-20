"""The quiet-hours warning states the bare fact: an old accepted event — even
commitless, even with no driver alive — yields exactly 'nothing accepted for
N hours', with no claim about what the loop is doing."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import view
import view_pulse

EXPECTED_TESTS = 2


class QuietHoursTest(unittest.TestCase):
    def test_a_commitless_acceptance_with_no_driver_states_the_bare_fact(self):
        camp = pathlib.Path(tempfile.mkdtemp())
        rows = [{"kind": "accepted", "task": "T1", "at": "2026-08-31T05:00:00Z"}]

        class StubSpace:
            def __init__(self, *a): pass
            def events(self): return rows
            def alerts(self): return []

        with unittest.mock.patch.object(view, "Workspace", StubSpace), \
             unittest.mock.patch.object(view, "CAMPAIGN", camp), \
             unittest.mock.patch.object(view_pulse, "CAMPAIGN", camp), \
             unittest.mock.patch.object(view, "driver_missing", lambda *a: ""), \
             unittest.mock.patch.object(view, "_supervisor_last_word", lambda: ([], 0.0)), \
             unittest.mock.patch.object(view, "base_measure", lambda *a, **k: ""), \
             unittest.mock.patch.object(view, "_driver_start", lambda *a, **k: None), \
             unittest.mock.patch.object(view, "_driver_pid", lambda *a, **k: None), \
             unittest.mock.patch.object(view, "calls_in_flight", list), \
             unittest.mock.patch.object(view, "driver_is_working", lambda *a, **k: False), \
             unittest.mock.patch("doctor.diagnose", lambda *a, **k: []):
            lines = view.warnings()
        quiet = [line for line in lines if "nothing accepted for" in line]
        self.assertEqual(1, len(quiet))
        self.assertRegex(quiet[0], r"nothing accepted for \d+ hours")
        self.assertNotIn("loop is", quiet[0])                   # no claim beyond the fact


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
