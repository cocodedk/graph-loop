"""The round's card is one dictionary, whatever the round writes on it.

A round whose recorded worktree is gone re-reads the card after clearing the
pointer (`loop.py`), and that read used to REPLACE the round's dictionary — so
the lane outside still held the older copy. Every field the loop itself writes
after that (the frozen `requirement`, the accepted contract's digest) landed on
one dictionary and not the other, and the lane's own guard then read its card as
edited by somebody else: a builder that crashed left the card `todo`, claimed by
nobody, instead of parked `lane_failed`. The rigs are `test_loop`'s and
`test_lanes`'s, joined.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from test_loop import Fakes, loop_for, task
from turn import run_lanes

EXPECTED_TESTS = 2


class Dying(Fakes):
    def builder(self, prompt, **kwargs):
        raise ZeroDivisionError("the builder died mid-round")


class LostTreeTest(unittest.TestCase):
    def test_a_builder_that_died_after_a_lost_tree_still_parks_its_card(self):
        loop, book, space = loop_for(task(rebuild_from="/nonexistent/tree"), Dying())
        run_lanes(loop, book, space, book.tasks())
        self.assertEqual("lane_failed", book.task("T1")["status"])
        self.assertTrue(space.alerts())            # and the death is still heard

    def test_a_re_read_that_could_not_be_written_leaves_the_card_readable(self):
        # The write itself fails — a full disk, an unwritable backlog. Emptying
        # the round's dictionary before that write lost the card's own id, and
        # every line of the lane's cleanup then raised `KeyError('id')`: no
        # failure recorded, no alert, the claim still held and the card `todo`.
        loop, book, space = loop_for(task(rebuild_from="/nonexistent/tree"), Dying())
        with mock.patch.object(Backlog, "note", side_effect=OSError("the backlog is unwritable")):
            run_lanes(loop, book, space, book.tasks())
        self.assertEqual("lane_failed", book.task("T1")["status"])
        self.assertTrue(space.alerts())
        self.assertEqual({}, space.running())      # and nothing is left claimed


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
