"""needs_slice counts the gate failures since the card was last dealt with.

A card parked as `needs_slice` is routed to a replan (`turn.py` writes
`replanned`) or to the slicer (`slice_finished`), and then runs again under the
same id. Its two old matching failures stayed in the log, so the first failure
of its new life parked it again — old failures condemning a card whose contract
had just been rewritten, the same fault the watchdog's own boundary already
answers for a spin. A boundary spends the failures of ITS OWN task only.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from workspace import Workspace

EXPECTED_TESTS = 6

WHY = "AssertionError on line 40"


def fresh() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="backlog.yaml")


def failed(space: Workspace, task: str = "T1", why: str = WHY) -> None:
    space.attempt(task, account="gate", kind="ok", failed_gate=True)
    space.event("failed", task=task, step="gate", why=why)


class SliceBoundaryTest(unittest.TestCase):
    def test_failures_before_a_replan_no_longer_ask_for_a_slice(self):
        space = fresh()
        failed(space)
        failed(space)
        self.assertTrue(space.needs_slice("T1"))
        space.event("replanned", task="T1", why="rewritten from the reviewer's findings")
        failed(space)
        self.assertFalse(space.needs_slice("T1"))

    def test_two_failures_after_the_boundary_ask_again(self):
        space = fresh()
        failed(space)
        space.event("slice_finished", task="T1", rc=0, state="planned")
        failed(space)
        failed(space)
        self.assertTrue(space.needs_slice("T1"))

    def test_another_cards_boundary_does_not_spend_this_ones_failures(self):
        space = fresh()
        failed(space)
        space.event("replanned", task="T2", why="a different card")
        failed(space)
        self.assertTrue(space.needs_slice("T1"))


class RefusedSliceTest(unittest.TestCase):
    """`slice_finished` is written for every answered slicer call, refusals
    included (slice_outcome.py). Only a slice that planned — rc 0 — rewrote the
    card, so only that one answers the failures before it."""

    def test_a_refused_slice_does_not_spend_the_failures(self):
        space = fresh()
        failed(space)
        failed(space)
        space.event("slice_finished", task="T1", rc=2, state="validation_refused",
                    why="the atoms do not cover the card")
        self.assertTrue(space.needs_slice("T1"))

    def test_a_slicer_nobody_answered_does_not_spend_the_failures(self):
        space = fresh()
        failed(space)
        failed(space)
        space.event("slice_finished", task="T1", rc=1, state="planner_unavailable",
                    why="the planner did not answer")
        self.assertTrue(space.needs_slice("T1"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
