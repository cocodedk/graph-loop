"""A live-stack lock nobody can read stops being a card's whole future.

An empty or garbled lock record is held, never free — a doubt never abandons
someone else's claim, and `test_live_lock` holds that. But nothing could be
asked whether that holder lives, so the card came back `waiting` every turn and
never reached an actor at all (astra round 4, finding 10). The lock file stays,
because what cannot be read cannot be cleared; the failure is recorded, and at
`LOCK_WAITS` the card carries that failure as its reason and leaves the queue:
the plan phase drops a card the loop itself parked, with the gap named. The rig
is `test_loop`'s, whose lock folder is the suite's own.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from plan_phase import drop_loop_holds
from test_loop import Fakes, loop_for, task
from worktree import LOCK_WAITS

EXPECTED_TESTS = 1


class UnreadableLiveLockTest(unittest.TestCase):
    def test_a_card_waiting_on_an_unreadable_lock_leaves_the_queue(self):
        loop, book, space = loop_for(
            task(gate_has_side_effects=True, gate="true", helper_verbs=["journal"]), Fakes())
        loop.lock.path.parent.mkdir(parents=True, exist_ok=True)
        loop.lock.path.write_text("", "utf-8")     # no pid, no start tick: no holder to ask
        # one folder holds this lock for the whole process (`tests/tmp_root.py`),
        # so an unreadable record left here is every later live test's lock too
        self.addCleanup(loop.lock.path.unlink, True)
        for _ in range(LOCK_WAITS):
            self.assertEqual("waiting", loop.run_task(book.task("T1")).state)
        self.assertTrue(loop.lock.path.exists())   # what cannot be read is not cleared
        self.assertIn("live_lock_unreadable", [row.get("kind") for row in space.events()])
        row = book.task("T1")
        self.assertIn("no holder", str(row.get("refused_why")))
        self.assertEqual(1, drop_loop_holds(book, space))
        gone = book.task("T1")
        self.assertEqual("dropped", gone["status"])
        self.assertIn("no holder", str(gone.get("refused_why")))   # the gap, named


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
