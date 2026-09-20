"""Retiring a child releases the parent's wait first, so a crash cannot orphan it.

`retire` renamed the stale child away and only then released the parent's wait
for it. A process that died between those two writes left a parent waiting for a
folder that is already gone, and no later pass could notice: recovery selects a
stale CHILD, and there is no child left to select, so the wait stood for ever and
the next publication, whose waits are the parent's, inherited it (Codex on
f1ae4c0f, finding 1).

Releasing the wait first makes the interruption recoverable instead. The child is
still readable with the parent already free, and the next pass calls it stale and
renames it, which is the end state either way.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "graph" / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import tree_stale
from test_stale_child_is_retired import staled
from test_tree import task
from tree import publish, recover

EXPECTED_TESTS = 3


class Interrupted(Exception):
    """The process dying, at one named point between the two writes."""


class RetireSurvivesAnInterruptionTest(unittest.TestCase):
    def setUp(self):
        self.repo, self.book = staled(keep_waits=True)
        self.backlog = self.repo / "backlog"
        self.assertEqual(["small"], self.book.task("large")["needs"])

    def _die(self, *, child_gone: bool):
        """Interrupt at a `_sync` chosen by whether the rename has happened yet.

        `book.note` syncs the backlog itself, so a mock that raises on the first
        call lands inside the note and never reaches the rename (Codex on
        87febf49, finding 1). The child folder is what tells the two apart.
        """
        real = tree_stale.durable._sync

        def sync(where):
            real(where)
            if (not (self.backlog / "small").exists()) is child_gone:
                raise Interrupted

        return mock.patch.object(tree_stale.durable, "_sync", side_effect=sync)

    def test_a_crash_after_the_rename_leaves_no_parent_waiting_for_a_gone_child(self):
        with self._die(child_gone=True), self.assertRaises(Interrupted):
            recover(self.backlog, "large")

        self.assertFalse((self.backlog / "small").exists(), "the rename never happened")
        self.assertEqual([], self.book.task("large")["needs"] or [],
                         "the parent is still waiting for the child that was renamed away")
        publish(self.backlog, task("fresh"), "large")
        self.assertEqual([], self.book.task("fresh")["needs"] or [],
                         "the replacement inherited the broken wait")

    def test_the_next_pass_finishes_what_a_crash_after_the_rename_left(self):
        with self._die(child_gone=True), self.assertRaises(Interrupted):
            recover(self.backlog, "large")

        recover(self.backlog, "large")     # whatever is left, a second pass settles it

        self.assertIsNone(self.book.task("small"))
        self.assertEqual([], self.book.task("large")["needs"] or [])

    def test_the_next_pass_finishes_what_a_crash_before_the_rename_left(self):
        """The wait is released first, so the earlier interruption leaves the
        child readable and the parent free: the next pass retires it."""
        with self._die(child_gone=False), self.assertRaises(Interrupted):
            recover(self.backlog, "large")

        self.assertTrue((self.backlog / "small").exists(), "the rename already happened")

        recover(self.backlog, "large")

        self.assertIsNone(self.book.task("small"))
        self.assertEqual([], self.book.task("large")["needs"] or [])
        self.assertFalse((self.backlog / "small").exists(),
                         "the stale child is still in the reader's way")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
