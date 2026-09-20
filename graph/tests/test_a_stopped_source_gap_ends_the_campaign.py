"""A source gap stopped at needs-a-person ends the campaign, and says so.

Campaign 7 built every buildable card and could not end. The gap had asked for
a person, so `covered_since_planning` was false for ever and `stand_down`
returned 1 every round. The supervisor read the fifth quick exit as the driver
dying and told a person so, which was false and is what would have been emailed.

The events here are campaign 7's own, from its `events.jsonl`: the sources
declared, three cards published off the gap, then `slice_needs_person`.

Companion to test_unfinished_work_is_not_a_finish.py, which covers the cards.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import source_gap
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from campaigns import CODE, campaign
from finishing import ENDED_WITH_GAPS, stand_down

EXPECTED_TESTS = 2
REFUSED = ("The only uncovered claim left is turning the fetched page into the "
           "post's text, and no source here declares that page's format")


def stopped_campaign():
    """Campaign 7's record, cut to what the ending is decided from."""
    book, space = campaign([{"id": "T1", "status": "done", **CODE}])
    space.event("sources_declared", sources=["docs/goal.md"])
    space.event("plan_started")
    space.event("slice_finished", task=source_gap.SOURCE_GAP, rc=0, state="published",
                why="published: recognize-x-post-link")
    space.event("slice_needs_person", task=source_gap.SOURCE_GAP, why=REFUSED)
    space.event("plan_started")
    return book, space


class StoppedGapTest(unittest.TestCase):
    def test_it_ends_with_the_gap_the_slicer_named(self):
        book, space = stopped_campaign()

        self.assertEqual(ENDED_WITH_GAPS, stand_down(space, book))
        gaps = source_gap.ended(space)
        assert gaps is not None
        self.assertIn("no source here declares that page's format", gaps["gaps"])

    def test_a_gap_that_may_still_be_sliced_is_not_an_ending(self):
        book, space = campaign([{"id": "T1", "status": "done", **CODE}])
        space.event("sources_declared", sources=["docs/goal.md"])
        space.event("plan_started")

        self.assertEqual(1, stand_down(space, book))
        self.assertIsNone(source_gap.ended(space))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
