"""A builder that moved HEAD does not write over a decision made while it ran.

`worktree_refs.discard` is the fourth writer of astra round 4 finding 2: after
a paid builder call it wrote `todo` — or `rejected` at the cap — straight onto
the card, so a drop decided in that hour came back as work to build again. What
the tree HOLDS is still saved first: the salvage is the loop's own pointer at
paid work, not a decision about the card, and losing it would lose the work
this guard exists to protect. The rig is `test_loop`'s, with the HEAD-moving
builder from `test_a_moved_head_keeps_its_edits`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_a_moved_head_keeps_its_edits import builder_that_commits
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 1


def commits_and_is_dropped(book):
    """The builder moves HEAD off the base, and the card is dropped meanwhile."""

    def builder(prompt, **kwargs):
        out = builder_that_commits(prompt, **kwargs)
        book.set_status("T1", "dropped", refused_why="decided against")
        return out

    return builder


class DiscardCardMovedTest(unittest.TestCase):
    def test_a_card_dropped_while_the_builder_moved_head_stays_dropped(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(triage="work"), fakes)
        loop.build = commits_and_is_dropped(book)
        out = loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertEqual("dropped", row.get("status"))
        self.assertEqual("held", out.state)          # no later writer acts on it
        self.assertIn("card_moved", [line.get("kind") for line in space.events()])
        self.assertTrue(row.get("lost_edits"), row)  # the paid work is still written down


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
