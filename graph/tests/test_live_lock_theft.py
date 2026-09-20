"""The live-stack lock is never taken from a living holder — not even by its
own task id.

astra's review, finding 7: `take` gave the lock back when the record named
the same task, so a second driver running the same card walked straight
through a holder that was alive and working. Whose task it is decides
nothing; whether the holder is gone decides everything.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import workspace_claims
from worktree import LiveLock

EXPECTED_TESTS = 1


class SameTaskTest(unittest.TestCase):
    def test_a_live_holder_keeps_the_lock_against_its_own_task_id(self):
        folder = tempfile.mkdtemp()
        # A living process (this one) holds the stack for T2; a second driver
        # then reaches T2 as well. The record names the same task, so the old
        # `holder() == task_id` shortcut freed a lock nobody had let go of.
        (pathlib.Path(folder) / "live-stack.lock").write_text(
            f"T2 {os.getpid()} {workspace_claims._started(os.getpid())}", "utf-8")

        self.assertFalse(LiveLock(folder).take("T2"))
        self.assertEqual("T2", LiveLock(folder).holder())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
