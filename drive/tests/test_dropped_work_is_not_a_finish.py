"""A campaign that dropped work ends with its gaps, never with zero.

Zero tells `supervisor.sh` the backlog is worked out and it stands down for
good. Without declared sources the backlog IS the whole job, and `stand_down`
returned zero for it whatever the backlog held — so a card the decider dropped
unproved was reported as a finish. `dropped` settles a dependency; it does not
prove the requirement (astra's round-3 finding 20).
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import source_gap
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from campaigns import campaign
from finishing import ENDED_WITH_GAPS, stand_down

EXPECTED_TESTS = 4
DONE = {"id": "T1", "status": "done", "goal": "read the journal", "files": ["a.py"],
        "gate": "true", "needs": []}
GONE = {"id": "T2", "status": "dropped", "goal": "prove the broker replays",
        "files": ["b.py"], "gate": "true", "needs": [],
        "refused_why": "no approved source names the broker journal"}


class DroppedWorkTest(unittest.TestCase):
    def test_a_dropped_card_ends_the_campaign_with_its_gap(self):
        book, space = campaign([dict(DONE), dict(GONE)])
        space.event("dropped", task="T2", why=GONE["refused_why"])

        self.assertEqual(ENDED_WITH_GAPS, stand_down(space, book))
        gaps = source_gap.ended(space)
        assert gaps is not None
        self.assertIn("T2", gaps["gaps"])
        self.assertIn("broker journal", gaps["gaps"])
        self.assertTrue(gaps["backlog"])          # what it left, digested

    def test_a_backlog_worked_out_still_finishes(self):
        book, space = campaign([dict(DONE)])
        self.assertEqual(0, stand_down(space, book))
        self.assertIsNone(source_gap.ended(space))

    def test_a_drop_replaces_a_finish_and_never_a_restart(self):
        """Exit 1 is not an ending: the supervisor starts another driver and
        the slicer plans the source gap again — and it is shown the dropped
        cards' contracts so it can plan around them. Ending there would stop a
        campaign that still has planning to do."""
        book, space = campaign([dict(DONE), dict(GONE)])
        space.event("sources_declared", sources=["docs/spec.md"])

        self.assertEqual(1, stand_down(space, book))   # coverage never proved this run
        self.assertIsNone(source_gap.ended(space))     # and nothing was ended

    def test_a_skipped_planning_attempt_is_temporary_and_still_restarts(self):
        """A skip judged nothing: the checkout could not be cut, so the gap was
        never put to the slicer at all. It clears the proof an earlier turn
        left, and the answer is another driver — a dropped card must not turn
        that temporary failure into an ending nothing retries (Codex on
        911bf81d, finding 1)."""
        book, space = campaign([dict(DONE), dict(GONE)])
        space.event("sources_declared", sources=["docs/spec.md"])
        space.event("driver_started", pid=1)
        space.event("slice_finished", task=source_gap.SOURCE_GAP, rc=0)
        space.event("slice_skipped", task=source_gap.SOURCE_GAP,
                    why="no clean checkout of campaign/drive: could not cut one")

        self.assertEqual(1, stand_down(space, book))
        self.assertIsNone(source_gap.ended(space))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
