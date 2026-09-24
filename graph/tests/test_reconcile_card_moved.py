"""A keep the branch holds but the card never recorded is not closed over a
decision made since the crash.

The turn top closes a keep whose card-write was lost: the branch holds the
commit, so the card must say so. But whatever held or edited the card between
the crash and the restart is newer than the keep — closing it there buries that
decision. The commit and the newer card both stand instead, and the mismatch is
written off mechanically (P3 § 1: nothing here waits for a person). What that
write-off leaves behind is `test_old_keep_cannot_finish_new_card`; here only
that the newer card survives it. The rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import publishing
from backlog import Backlog
from loop import Loop
from test_loop import Fakes, repo_with, task
from workspace import Workspace

EXPECTED_TESTS = 3


def dropper(book, started: list):
    """A stand-in for `Workspace.events` — reconcile's own read between the card
    and the write — that lets a SECOND writer drop the card in that window.

    A thread, not a plain call: `Backlog.only_writer` is reentrant within one
    thread, so a same-thread write would slip through the very lock this is
    about. The wait returns at once while the lock is free, which is the window,
    and times out while reconcile holds it.
    """
    real = Workspace.events
    wrote = threading.Event()

    def drop():
        book.set_status("T1", "dropped")
        wrote.set()

    def events(self):
        if not started:
            started.append(threading.Thread(target=drop, daemon=True))
            started[0].start()
            wrote.wait(0.5)
        return real(self)

    return events


class ReconcileCardMovedTest(unittest.TestCase):
    def setUp(self):
        """T1 kept, then the driver dies exactly where it died in the record:
        the ref has moved and the card-write raised."""
        fakes = Fakes()
        self.root, self.book, self.space = repo_with(task())
        self.loop = Loop(repo=self.root, backlog=self.book, space=self.space,
                         build=fakes.builder, review=fakes.reviewer,
                         branch="campaign/test")
        real = Backlog.set_status

        def crash_on_done(book, task_id, status, **fields):
            if status == "done":
                raise ZeroDivisionError("the driver died after the ref moved")
            return real(book, task_id, status, **fields)

        with mock.patch.object(Backlog, "set_status", crash_on_done), \
                self.assertRaises(ZeroDivisionError):
            self.loop.run_task(self.book.task("T1"))
        self.note = pathlib.Path(self.root, ".git", "keep-pending-campaign%2Ftest-T1")
        self.assertTrue(self.note.exists())
        self.assertNotEqual("done", self.book.task("T1")["status"])

    def test_a_card_held_after_the_crash_keeps_the_hold_and_the_commit(self):
        commit = self.note.read_text("utf-8").strip()
        self.book.note("T1", blocked_by_human=True)
        publishing.reconcile(self.loop, self.book, self.space)
        row = self.book.task("T1")
        self.assertNotEqual("done", row["status"])
        self.assertTrue(row["blocked_by_human"])
        # The note is written off rather than kept for a person; the commit it
        # named is still on the branch, which is what preserving it means.
        held = subprocess.run(("git", "-C", self.root, "merge-base", "--is-ancestor",
                               commit, "campaign/test"), capture_output=True, check=False)
        self.assertEqual(0, held.returncode)

    def test_a_card_nobody_touched_is_still_closed_and_settled(self):
        publishing.reconcile(self.loop, self.book, self.space)
        self.assertEqual("done", self.book.task("T1")["status"])
        self.assertFalse(self.note.exists())

    def test_a_card_dropped_while_the_keep_reconciled_stays_dropped(self):
        # The revision matched when it was read: the decision lands INSIDE the
        # window between that read and the write, so only one lock hold saves it.
        started: list = []
        with mock.patch.object(Workspace, "events", dropper(self.book, started)):
            publishing.reconcile(self.loop, self.book, self.space)
        started[0].join(5)
        self.assertEqual("dropped", self.book.task("T1")["status"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
