"""The live-stack lock belongs to the stack, not to the campaign that wants it.

Round 2, finding 6. Every builder addresses the one stack the helper drives
(`graph-live`), but the lock lived in the campaign's own directory: a second
campaign started on the same host simply had its own file, took it, and drove
the same stack alongside the first. And `give_back` unlinked whatever was
there, so a driver that never took the lock could free another's.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_loop import Fakes, loop_for, task
from worktree import LiveLock

EXPECTED_TESTS = 3
LIVE = {"gate_has_side_effects": True, "gate": "true", "helper_verbs": ["journal"]}


class SharedStackTest(unittest.TestCase):
    def test_a_second_campaign_waits_on_the_stack_the_first_holds(self):
        # where the one host-wide lock lives is stood in for, never moved by an
        # environment variable: a driver may be holding the real one
        self.enterContext(unittest.mock.patch("worktree_lock.shared",
                                              return_value=tempfile.mkdtemp()))
        first, _, _ = loop_for(task(**LIVE), Fakes())
        second, book, _ = loop_for(task(**LIVE), Fakes())    # its own repo, backlog, campaign
        self.assertTrue(first.lock.take("T1"))
        out = second.run_task(book.task("T1"))
        self.assertEqual("waiting", out.state, out.why)


class OwnerReleasesTest(unittest.TestCase):
    def test_a_driver_that_never_took_the_lock_cannot_free_it(self):
        folder = tempfile.mkdtemp()
        holder, other = LiveLock(folder), LiveLock(folder)
        self.assertTrue(holder.take("T1"))
        self.addCleanup(holder.give_back)
        other.give_back()
        self.assertEqual("T1", other.holder())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
