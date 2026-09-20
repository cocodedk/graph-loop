"""A keep the card has outgrown is retired by a receipt, never by a person.

The branch holds a commit whose card-write was lost, and the card was decided
again after that keep. Closing the card would bury the newer decision, so the
old code kept the note and alerted a person to close it by hand. Nothing in
this loop waits for a person to read text (CLAUDE.md § Code), so the mismatch
is now written down instead: a durable receipt naming the commit and both
revisions, that exact note retired, the commit left on the branch and the newer
card left exactly as it stands.

The rig is `test_reconcile_card_moved`'s: T1 kept, then a death between the ref
move and the card write.
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


class OldKeepTest(unittest.TestCase):
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

    def test_old_keep_cannot_finish_new_card(self):
        self.book.note("T1", blocked_by_human=True)      # the card was decided again
        publishing.reconcile(self.loop, self.book, self.space)

        row = self.book.task("T1")
        self.assertNotEqual("done", row["status"])       # the newer card is not closed
        self.assertTrue(row["blocked_by_human"])         # and its hold is not cleared
        self.assertFalse(self.note.exists())             # that exact note is retired

        receipt = json.loads(publishing.receipt_path(
            self.space, "T1", self.commit).read_text("utf-8"))
        self.assertEqual(self.commit, receipt["commit"])
        self.assertTrue(receipt["kept_at_revision"])     # the revision it was kept at
        self.assertNotEqual(receipt["kept_at_revision"], receipt["card_revision"])
        self.assertTrue(receipt["settled"])              # nothing is left owed

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
