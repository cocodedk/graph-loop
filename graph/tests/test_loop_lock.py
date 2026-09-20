"""B2: the live lock is taken INSIDE the try, so a failure between taking it
and finishing the task -- `Worktree.create` raising, the record write failing
-- still runs `finally` and gives the lock back. Before this fix the lock was
taken before the try even started, and a crash there left the lock file on
disk for every later live card to wait on forever."""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from test_loop import Fakes, loop_for, task
from worktree import Worktree

EXPECTED_TESTS = 3


class LockInsideTryTest(unittest.TestCase):
    def test_a_crash_taking_the_worktree_still_gives_the_lock_back(self):
        fakes = Fakes()
        loop, book, _ = loop_for(
            task(gate_has_side_effects=True, gate="true", helper_verbs=["journal"]), fakes)
        with (unittest.mock.patch.object(
                Worktree, "create", side_effect=RuntimeError("no space left on device")),
              self.assertRaises(RuntimeError)):
            loop.run_task(book.task("T1"))
        self.assertFalse(loop.lock.path.exists())


class PeerReleaseFailsTest(unittest.TestCase):
    """A failure releasing the peers must not skip giving the lock back --
    `release_live_peers` raises AFTER a task finishes clean, and the lock
    must still be freed, or every later live card waits on it forever."""

    def test_a_failing_peer_release_still_gives_the_lock_back(self):
        fakes = Fakes()
        loop, book, _ = loop_for(
            task(gate_has_side_effects=True, gate="true", helper_verbs=["journal"]), fakes)
        with (unittest.mock.patch("loop.release_live_peers",
                                  side_effect=RuntimeError("backlog write failed")),
              self.assertRaises(RuntimeError)):
            loop.run_task(book.task("T1"))
        self.assertFalse(loop.lock.path.exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
