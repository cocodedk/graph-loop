"""A restart already asked for silences one line, never the whole board.

`warnings` returned early when restart.flag existed, so every check after the
stale-driver line was skipped. An expired account sat unreported behind a
pending restart on 2026-08-31.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import doctor
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import view
from doctor_types import Complaint

EXPECTED_TESTS = 1

REAL_EXISTS = pathlib.Path.exists


def restart_is_pending(self: pathlib.Path) -> bool:
    return True if self.name == "restart.flag" else REAL_EXISTS(self)


class ARestartDoesNotSilenceTheBoard(unittest.TestCase):
    def test_the_doctors_complaints_survive_a_pending_restart(self):
        import tempfile

        import view_pulse
        said = Complaint("an account", "a session has expired", "sign it in again")
        camp = pathlib.Path(tempfile.mkdtemp())   # one temp campaign for BOTH modules,
        # or health() inside warnings() writes the live campaign's flags-seen.json
        with unittest.mock.patch.object(doctor, "diagnose", lambda *a, **k: [said]), \
             unittest.mock.patch.object(view, "_driver_start", lambda *a, **k: 0.0), \
             unittest.mock.patch.object(view, "CAMPAIGN", camp), \
             unittest.mock.patch.object(view_pulse, "CAMPAIGN", camp), \
             unittest.mock.patch.object(pathlib.Path, "exists", restart_is_pending):
            lines = view.warnings()
        self.assertTrue(any("a session has expired" in line for line in lines),
                        "a pending restart hid the doctor's complaints")


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
