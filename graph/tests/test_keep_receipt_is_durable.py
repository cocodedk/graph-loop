"""Retiring a superseded keep's note is finished on the platter, or not at all.

Two ways the write-off could lie to the next start (an independent review):

The note's removal is a directory entry, and an entry that never reached the
platter comes back. A receipt marked settled over it leaves recovery skipping a
note ordinary reconciliation will meet again — the very thing the receipt
exists to stop — so the parent is fsynced before the settlement is recorded,
whether this call removed the note or found it already gone.

And a note nobody could READ is not a note that is gone: catching every
`OSError` marked such a receipt settled and left the note standing. Only
"there is no such file" is an answer; anything else is raised, and the receipt
stays owed.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import durable
import publishing
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from workspace import Workspace

EXPECTED_TESTS = 3
SHA = "a" * 40


def receipt_for(space, note: pathlib.Path) -> pathlib.Path:
    """One superseded-keep receipt, as `supersede` leaves it before retiring."""
    path = publishing.receipt_path(space, "T1", SHA)
    durable.replace(path, json.dumps(
        {"task": "T1", "commit": SHA, "kept_at_revision": "one",
         "card_revision": "two", "note": str(note), "at": "now", "settled": ""},
        sort_keys=True, indent=1))
    return path


class DurabilityTest(unittest.TestCase):
    def setUp(self):
        self.space = Workspace(pathlib.Path(tempfile.mkdtemp()))
        self.notes = pathlib.Path(tempfile.mkdtemp())

    def order_of(self, note: pathlib.Path) -> list:
        """What `settle_superseded` puts on the platter, in the order it does."""
        path = receipt_for(self.space, note)
        seen: list = []
        real_sync, real_replace = durable._sync, durable.replace

        def sync(folder):
            seen.append(("sync", pathlib.Path(folder)))
            return real_sync(folder)

        def replace(where, data):
            seen.append(("replace", pathlib.Path(where)))
            return real_replace(where, data)

        with mock.patch.object(durable, "_sync", sync), \
                mock.patch.object(durable, "replace", replace):
            publishing.settle_superseded(self.space)
        self.assertTrue(json.loads(path.read_text("utf-8"))["settled"])
        return seen

    def test_the_note_is_gone_from_the_platter_before_the_receipt_settles(self):
        note = self.notes / "keep-pending-campaign%2Ftest-T1"
        note.write_text(SHA, "utf-8")
        seen = self.order_of(note)
        self.assertFalse(note.exists())
        self.assertLess(seen.index(("sync", self.notes)),
                        seen.index(("replace", publishing.receipt_path(self.space, "T1", SHA))))

    def test_a_note_already_gone_is_still_synced_before_the_receipt_settles(self):
        """The unlink that removed it may itself have died in the page cache;
        recording settlement over that would restore the note and lose the
        receipt with it."""
        seen = self.order_of(self.notes / "keep-pending-campaign%2Ftest-T1")
        self.assertLess(seen.index(("sync", self.notes)),
                        seen.index(("replace", publishing.receipt_path(self.space, "T1", SHA))))

    def test_a_note_that_cannot_be_read_leaves_the_receipt_owed(self):
        unreadable = self.notes / "keep-pending-campaign%2Ftest-T1"
        unreadable.mkdir()          # a read failure that is not "no such file"
        path = receipt_for(self.space, unreadable)
        with self.assertRaises(OSError):
            publishing.settle_superseded(self.space)
        self.assertFalse(json.loads(path.read_text("utf-8"))["settled"])
        self.assertTrue(unreadable.exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
