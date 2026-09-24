"""A hold raised mid-round survives a rejection, wherever in the round it lands.

Every ending that is not a keep requeues the card as `todo`, and `_apply`
clears a hold on a requeue: a person who held the card while the builder ran
had the hold dropped and the card charged a round for a finding about a
contract they were in the middle of changing.

Two windows, one rule. A hold written BEFORE the ending starts is caught by
the guard, and the round costs nothing. A hold written while the ending runs
is serialised behind it: the ending's read and its write are one lock hold, so
the hold lands after and stands. The rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_keep_card_moved import after_the_build
from test_loop import Fakes, loop_for, task
from worktree import Worktree

EXPECTED_TESTS = 4

ACCEPT = Outcome("ok", verdict="ACCEPT", text="ok")


def writer_during_keep(book, started: list):
    """A stand-in for `Worktree.keep` that lets a SECOND writer try to hold the
    card while the round is between its guard and its status write.

    A thread, not a plain call: `Backlog.only_writer` is reentrant within one
    thread, so a same-thread write would slip through the very lock this is
    about and prove nothing. The wait returns at once while the lock is free —
    which is the window — and times out while the round holds it.
    """
    real = Worktree.keep
    wrote = threading.Event()

    def hold():
        book.note("T1", blocked_by_human=True)
        wrote.set()

    def keep(self, why):
        if not started:
            started.append(threading.Thread(target=hold, daemon=True))
            started[0].start()
            wrote.wait(0.5)
        return real(self, why)

    return keep


class HeldThenRejectedTest(unittest.TestCase):
    def test_a_hold_survives_a_rejected_diff_and_costs_no_round(self):
        fakes = Fakes(review=[ACCEPT, Outcome("ok", verdict="REJECT", text="1. wrong line")])
        loop, book, _ = loop_for(task(), fakes)
        loop.build = after_the_build(fakes, book, blocked_by_human=True)
        out = loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertTrue(row["blocked_by_human"])                 # the hold stands
        self.assertEqual(0, int(row.get("rebuild_round") or 0))  # nothing charged
        self.assertEqual(out.worktree, row["rebuild_from"])      # the paid tree is named

    def test_a_hold_survives_a_harness_fault_and_costs_no_round(self):
        # back_in_place, not _send_back: the same write, the same clearing.
        fakes = Fakes(review=[ACCEPT, Outcome("crash", text="the reviewer died")])
        loop, book, _ = loop_for(task(), fakes)
        loop.build = after_the_build(fakes, book, blocked_by_human=True)
        out = loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertTrue(row["blocked_by_human"])
        self.assertEqual(0, int(row.get("rebuild_round") or 0))
        self.assertEqual(out.worktree, row["rebuild_from"])


class HeldBetweenGuardAndWriteTest(unittest.TestCase):
    """The guard reads the card and then the write lands: everything between
    the two must be inside one lock hold, or another writer's decision is
    read too early and overwritten a moment later."""

    def _run(self, review: list) -> dict:
        fakes = Fakes(review=review)
        loop, book, _ = loop_for(task(), fakes)
        started: list = []
        with mock.patch.object(Worktree, "keep", writer_during_keep(book, started)):
            loop.run_task(book.task("T1") or {})   # `or {}`: a vanished card fails loudly
        started[0].join(5)
        return book.task("T1") or {}

    def test_a_hold_written_during_a_rejection_is_not_cleared(self):
        row = self._run([ACCEPT, Outcome("ok", verdict="REJECT", text="1. wrong line")])
        self.assertTrue(row["blocked_by_human"])

    def test_a_hold_written_during_a_harness_fault_is_not_cleared(self):
        row = self._run([ACCEPT, Outcome("crash", text="the reviewer died")])
        self.assertTrue(row["blocked_by_human"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
