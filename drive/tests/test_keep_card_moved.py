"""A decision made WHILE the build and its reviews ran is not marked done over.

The keep is the last write of a round that took an hour. A hold raised in that
window, or a contract edited in it, is newer than the work about to be
published: the branch and the card keep the person's decision, and the paid
tree is kept for the round that reads the new contract. The rig lives in
`test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from loop import Loop
from test_loop import Fakes, loop_for, repo_with, task

EXPECTED_TESTS = 5


def keeper_loop(row: dict, fakes: Fakes):
    """A loop with a real Keeper: the done-write is the keeper's own callback."""
    root, book, space = repo_with(row)
    return Loop(repo=root, backlog=book, space=space, build=fakes.builder,
                review=fakes.reviewer, branch="campaign/test"), book, space


def after_the_build(fakes: Fakes, book, **edit):
    """A builder that answers, then a person writes on the card mid-round."""
    real = fakes.builder

    def builder(prompt, **kwargs):
        out = real(prompt, **kwargs)
        book.note("T1", **edit)
        return out

    return builder


class CardMovedTest(unittest.TestCase):
    def test_a_hold_raised_mid_round_stops_the_keep(self):
        fakes = Fakes()
        loop, book, space = keeper_loop(task(), fakes)
        loop.build = after_the_build(fakes, book, blocked_by_human=True)
        out = loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertNotEqual("done", row["status"])          # never published over
        self.assertTrue(row["blocked_by_human"])
        self.assertTrue(pathlib.Path(out.worktree).is_dir())   # the work is kept
        self.assertIn("card_moved", [e["kind"] for e in space.events()])

    def test_a_contract_edited_mid_round_is_not_marked_done(self):
        # No keeper: the done-write is the loop's own, and it must not land either.
        fakes = Fakes()
        loop, book, _ = loop_for(task(), fakes)
        loop.build = after_the_build(fakes, book, goal="make a.py say two, and only that")
        out = loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertNotEqual("done", row["status"])
        self.assertEqual("make a.py say two, and only that", row["goal"])
        self.assertEqual(out.worktree, row["rebuild_from"])   # the paid tree, not re-paid

    def test_a_card_dropped_mid_round_is_not_marked_done(self):
        # A status is a decision as much as a hold is: a person who drops the
        # card while the build runs must not find it done a minute later.
        fakes = Fakes()
        loop, book, space = loop_for(task(), fakes)
        loop.build = after_the_build(fakes, book, status="dropped")
        loop.run_task(book.task("T1"))
        self.assertEqual("dropped", book.task("T1")["status"])
        self.assertIn("card_moved", [e["kind"] for e in space.events()])

    def test_a_card_given_a_new_dependency_mid_round_is_not_marked_done(self):
        # `needs` says what this card must wait for. One added while the round
        # ran is newer than the round, and publishing over it starts work the
        # person just said comes second.
        fakes = Fakes()
        loop, book, space = loop_for(task(), fakes)
        loop.build = after_the_build(fakes, book, needs=["T0"])
        loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertNotEqual("done", row["status"])
        self.assertEqual(["T0"], row["needs"])
        self.assertIn("card_moved", [e["kind"] for e in space.events()])

    def test_a_note_shaped_like_the_wait_list_does_not_hide_a_new_dependency(self):
        # Codex, 2026-09-08: this card's note ends in the line its wait list
        # prints, so pasted into one contract text the two read the same and
        # the real dependency added mid-round disappeared from the comparison.
        fakes = Fakes()
        loop, book, space = loop_for(task(note='n\nwaits for: [\'T0\']'), fakes)
        loop.build = after_the_build(fakes, book, needs=["T0"], note="n")
        loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertNotEqual("done", row["status"])
        self.assertEqual(["T0"], row["needs"])
        self.assertIn("card_moved", [e["kind"] for e in space.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
