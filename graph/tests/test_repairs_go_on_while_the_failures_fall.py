"""A feature is not stopped while each repair round fixes more (issue #255).

One spec's parity check went 22 of 52 files identical, then 40 of 48, then 44 of 48, and stopped at the
repair limit; a manual rerun converged on the next round. A repair that leaves fewer failing lines than the
round before it now earns one more repair, up to `MOST_REPAIRS`; a round that does not lower the count
spends the rounds it was given.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_run
from gate_reports import failures
from test_lean_run import Rig

EXPECTED_TESTS = 7


def red(count):
    return "".join(f"FAIL case {n}\n" for n in range(count))


class Falling(Rig):
    def go(self, counts):
        suites = [False] * len(counts)
        if counts[-1] == 0:
            suites[-1] = True
        writes = [("ring.py", f"{n}\n") for n in range(len(counts))]
        url = self.run_it(self.builder(*writes), suites=suites, tails=[red(c) for c in counts if c])
        return url, len(self.prompts)

    def test_a_fall_earns_a_repair_beyond_the_usual_two(self):
        url, calls = self.go([5, 3, 1, 0])
        self.assertEqual((True, 4), (bool(url), calls))

    def test_no_fall_spends_only_the_rounds_it_was_given(self):
        url, calls = self.go([5, 5, 5, 5])
        self.assertEqual(("", 1 + lean_run.REPAIRS), (url, calls))

    def test_fewer_failed_tests_is_progress_though_the_lines_rise(self):
        tails = ["FAILED (failures=5)\n", "FAIL a\nFAIL b\nFAIL c\nFAILED (failures=3)\n",
                 "FAIL a\nFAIL b\nFAIL c\nFAIL d\nFAILED (failures=1)\n"]
        writes = [("ring.py", f"{n}\n") for n in range(4)]
        url = self.run_it(self.builder(*writes), suites=[False, False, False, True], tails=tails)
        self.assertEqual((True, 4), (bool(url), len(self.prompts)))

    def test_more_failed_tests_is_no_progress_though_the_lines_fall(self):
        tails = ["FAIL a\nFAIL b\nFAIL c\n3 failed\n", "4 failed\n", "5 failed\n"]
        writes = [("ring.py", f"{n}\n") for n in range(4)]
        url = self.run_it(self.builder(*writes), suites=[False] * 4, tails=tails)
        self.assertEqual(("", 1 + lean_run.REPAIRS), (url, len(self.prompts)))

    def test_a_summary_is_counted_from_its_last_line(self):
        self.assertEqual((3, 0), failures("1 failed\n== 2 failed, 1 error in 3s ==\n"))
        self.assertEqual((0, 2), failures("FAIL a\nFAIL b\n"))

    def test_a_fall_that_never_ends_stops_at_the_ceiling(self):
        url, calls = self.go([9, 8, 7, 6, 5, 4, 3])
        self.assertEqual(("", 1 + lean_run.MOST_REPAIRS), (url, calls))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())   # the six above and this one


if __name__ == "__main__":
    unittest.main()
