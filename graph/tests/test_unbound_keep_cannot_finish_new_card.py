"""A keep that names no card revision cannot close a card either.

The turn top closes a keep whose card-write was lost only while the card still
matches the `keep_revision` the keep was made against. A note with no revision on
the card — an older keep, a card written before the field existed — was let
through that check and closed whatever card it found, dropped or rewritten since.
Absent is unbound, not "it matches": it goes down the same superseded path, the
commit and the newer card both standing. The rig is `test_reconcile_card_moved`'s.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import publishing
from backlog import Backlog
from loop import Loop
from test_loop import Fakes, repo_with, task

EXPECTED_TESTS = 1


class UnboundKeepTest(unittest.TestCase):
    def setUp(self):
        """T1 kept, then the driver dies where it died in the record: the ref
        has moved and the card-write raised."""
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
        self.commit = self.note.read_text("utf-8").strip()

    def test_a_keep_with_no_revision_cannot_finish_a_dropped_card(self):
        # The card was dropped after the crash, and the keep names no revision
        # to compare it against.
        self.book.set_status("T1", "dropped", keep_revision=None,
                             refused_why="decided against")
        publishing.reconcile(self.loop, self.book, self.space)

        self.assertEqual("dropped", self.book.task("T1")["status"])   # not closed over
        self.assertFalse(self.note.exists())                          # that note is retired

        receipt = json.loads(publishing.receipt_path(
            self.space, "T1", self.commit).read_text("utf-8"))
        self.assertEqual("", receipt["kept_at_revision"])              # unbound, and said so
        self.assertTrue(receipt["settled"])                            # nothing left owed

        held = subprocess.run(("git", "-C", self.root, "merge-base", "--is-ancestor",
                               self.commit, "campaign/test"), capture_output=True, check=False)
        self.assertEqual(0, held.returncode)             # the commit stays on the branch


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
