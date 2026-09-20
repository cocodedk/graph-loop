"""A scope fault on a decided card does not become a re-slice either.

`gate_left_its_lane` leaves a card another writer decided while the gate ran
alone — but it still ended the round `failed`, and a lane reads that state: a
card that failed the same way twice is written `needs_slice` back in
`lanes.run_lanes`. So the decision the guard preserved was overwritten one frame
further out. A preserved card ends the round `held`, which no later writer acts
on. The rigs are `test_loop`'s and `test_lanes`'s, joined.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loop_evidence
import loop_judge_retry
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_loop import Fakes, loop_for, task
from turn import run_lanes
from workspace import Workspace

EXPECTED_TESTS = 1


def red_after_a_drop(book):
    """The gate proves red, with the card dropped while it ran."""

    def prove_red(command, cwd, expect="", **kwargs):
        book.set_status("T1", "dropped", refused_why="decided against")
        return True, "proved red"

    return prove_red


class ScopeFaultInALaneTest(unittest.TestCase):
    def test_a_scope_fault_on_a_decided_card_is_not_re_sliced_over_it(self):
        loop, book, space = loop_for(task(), Fakes())
        with mock.patch.object(loop_evidence, "prove_red", red_after_a_drop(book)), \
                mock.patch.object(loop_judge_retry, "changed_outside",
                                  lambda *a, **k: ["b.py"]), \
                mock.patch.object(Workspace, "needs_slice", lambda self, task_id: True):
            run_lanes(loop, book, space, book.tasks())
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertIn("card_moved", [row.get("kind") for row in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
