"""Card weight: how large a task looks from its own shape. Which model and
effort actually run is `model_router.choose`'s call now (docs/ROUTER.md);
the ladder this file tested is superseded, and `weight` alone remains."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from effort import weight

EXPECTED_TESTS = 3


def task(**extra) -> dict:
    row = {"id": "T1", "files": ["a.py"], "done_when": "a.py says two"}
    row.update(extra)
    return row


class WeightTest(unittest.TestCase):
    def test_a_small_card_weighs_nothing(self):
        self.assertEqual(0, weight(task()))

    def test_a_live_or_commander_marked_card_weighs_more(self):
        self.assertEqual(2, weight(task(gate_has_side_effects=True)))
        self.assertEqual(2, weight(task(hard_review=True)))

    def test_a_wide_card_or_a_long_contract_counts(self):
        wide = task(files=["a.py", "b.py", "c.py", "d.py"])
        self.assertEqual(1, weight(wide))
        self.assertEqual(1, weight(task(done_when="x" * 1300)))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
