"""The effort ladder: chosen per task from its own shape and from what already
failed — no pre-flight model call, and `max` on neither ladder."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from effort import BUILD_LADDER, REVIEW_LADDER, build_effort, review_effort

EXPECTED_TESTS = 5


def task(**extra) -> dict:
    row = {"id": "T1", "files": ["a.py"], "done_when": "a.py says two"}
    row.update(extra)
    return row


class LadderTest(unittest.TestCase):
    def test_max_is_on_neither_ladder(self):
        self.assertNotIn("max", BUILD_LADDER)
        self.assertNotIn("max", REVIEW_LADDER)

    def test_a_small_card_is_cheap_to_build_and_to_review(self):
        self.assertEqual("high", build_effort(task()))
        self.assertEqual("medium", review_effort(task()))

    def test_a_live_card_starts_at_the_top(self):
        row = task(gate_has_side_effects=True)
        self.assertEqual("xhigh", build_effort(row))
        self.assertEqual("high", review_effort(row))

    def test_a_round_that_failed_lifts_the_next_one(self):
        self.assertEqual("high", review_effort(task(rebuild_round=1)))
        self.assertEqual("high", review_effort(task(replans=2)))
        self.assertEqual("xhigh", build_effort(task(rebuild_round=1)))

    def test_a_wide_card_or_a_long_contract_counts(self):
        wide = task(files=["a.py", "b.py", "c.py", "d.py"])
        self.assertEqual("xhigh", build_effort(wide))
        self.assertEqual("high", review_effort(wide))
        self.assertEqual("high", review_effort(task(done_when="x" * 1300)))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
