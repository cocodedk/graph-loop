"""A driver running a gate is working, not stalled.

A gate writes no events, and the combined-tree gate before a keep runs several
suites: the board read that silence as a dead driver and said so every time.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from view_health import driver_is_working

EXPECTED_TESTS = 4


class ADriverWithChildrenIsWorking(unittest.TestCase):
    def test_a_driver_running_a_gate_is_working(self):
        rows = [["1000", "1"], ["2000", "1000"]]          # the gate is the driver's child
        self.assertTrue(driver_is_working(1000, rows))

    def test_a_driver_with_no_children_is_not(self):
        rows = [["1000", "1"], ["2000", "999"]]
        self.assertFalse(driver_is_working(1000, rows))

    def test_no_driver_is_not_working(self):
        self.assertFalse(driver_is_working(None, [["1000", "1"]]))

    def test_a_short_ps_row_is_ignored_rather_than_crashing(self):
        self.assertFalse(driver_is_working(1000, [["1000"], []]))


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
