"""The source gap is planned even while cards are startable.

The first real campaign run on this branch wrote one molecule and then stopped:
its atoms were `todo` the moment it was written, and `slice_pending` returned
without a call whenever anything was startable and nothing was stuck. So every
later molecule went unwritten and the plan phase ended after one (2026-09-18).

That rule was right while this ran at the top of a build turn — building beat
planning, because both were happening in the same turn. In a plan phase nothing
is building, so it only ever stopped the plan.

The rig is `test_turn_slice`'s.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import slice_turn
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_turn_slice import routed, router, space, tree_with

EXPECTED_TESTS = 3
STARTABLE = {"id": "T1", "status": "todo", "goal": "g", "files": ["app.py"],
             "gate": "false", "done_when": "x"}


class PlanPastTheFirstMoleculeTest(unittest.TestCase):
    def test_a_startable_card_does_not_hold_back_the_source_gap(self):
        book, campaign = tree_with(dict(STARTABLE)), space()
        route = router(unittest.mock.Mock(returncode=0, stdout="", stderr=""))
        with routed(route):
            slice_turn.slice_pending(book, campaign)
        self.assertEqual(1, len(route.slicer_calls),
                         "the gap went unplanned while a card was startable")

    def test_a_card_a_lane_is_building_still_is_not_the_target(self):
        """The half of `busy` that stays: a plan phase normally runs with the
        driver stopped, but a card another process has claimed is never
        rewritten under its own builder."""
        wall = {"id": "T1", "status": "needs_slice", "goal": "g", "files": ["app.py"],
                "triage": "work", "refused_why": "the gate said why"}
        book, campaign = tree_with(dict(wall)), space()
        route = router(unittest.mock.Mock(returncode=0, stdout="", stderr=""))
        with routed(route):
            slice_turn.slice_pending(book, campaign, taking=("T1",))
        for argv in route.slicer_calls:
            self.assertNotIn("--target", argv, "a card being built was sliced")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
