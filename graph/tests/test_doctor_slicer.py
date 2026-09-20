"""The slicer's own paid planning calls are never unkept builder work."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from doctor import check_costly_silence
from test_doctor import space

EXPECTED_TESTS = 1


class SlicerSpendTest(unittest.TestCase):
    def test_the_slicers_paid_planning_is_not_unkept_work(self):
        here = space()
        here.attempt("the slicer", account="work", kind="ok", cost=4.2)
        here.attempt("the slicer", account="personal", kind="limit", cost=4.1)
        self.assertEqual([], check_costly_silence(here))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
