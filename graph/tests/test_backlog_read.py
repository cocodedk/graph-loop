"""A reader never waits for a writer, and never sees half a file.

A reader used to wait behind a keep: `read` took the writer's lock, and a keep
holds that lock across a combined-tree gate. Two lanes slicing the same backlog
could also lose each other's pieces, because `slice_task` read under the lock
and wrote outside it.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog import Backlog

EXPECTED_TESTS = 3


def a_backlog(tmp: str) -> Backlog:
    path = pathlib.Path(tmp) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"tasks": [{"id": "T1", "status": "todo", "needs": []}]}))
    return Backlog(path)


class ReadingNeverWaits(unittest.TestCase):
    def test_read_returns_while_a_writer_holds_the_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = a_backlog(tmp)
            holding, release = threading.Event(), threading.Event()

            def writer():
                with book.only_writer():
                    holding.set()
                    release.wait(5)

            hand = threading.Thread(target=writer)
            hand.start()
            self.assertTrue(holding.wait(5))
            done = threading.Event()

            def reader():
                book.read()
                done.set()

            threading.Thread(target=reader).start()
            self.assertTrue(done.wait(2), "read() waited for the writer's lock")
            release.set()
            hand.join(5)

    def test_a_reader_sees_the_whole_old_document_while_a_write_is_half_done(self):
        """The reason `read` may drop the lock. A truncate-and-write leaves the
        file short mid-write; a rename never does.

        The pause sits at the rename because that is where the write now is:
        the new document is written to a sibling and fsynced (`durable.py`), so
        the reader below meets the writer at its widest window, with the whole
        replacement on disk and the old document still in place.
        """
        with tempfile.TemporaryDirectory() as tmp:
            book = a_backlog(tmp)
            halfway, seen = threading.Event(), []
            real = os.replace

            def slow_replace(source, target, *args, **kwargs):
                if pathlib.Path(target).name == "backlog.yaml":
                    halfway.set()
                    time.sleep(0.3)
                return real(source, target, *args, **kwargs)

            def writer():
                with unittest.mock.patch.object(os, "replace", slow_replace):
                    book.set_status("T1", "done")

            hand = threading.Thread(target=writer)
            hand.start()
            self.assertTrue(halfway.wait(5))
            seen.append(book.read())
            hand.join(5)
            self.assertEqual(seen[0]["tasks"][0]["status"], "todo",
                             "a reader saw a half-written document")
            self.assertEqual(book.read()["tasks"][0]["status"], "done")
            self.assertFalse(list(pathlib.Path(tmp).glob(".*.tmp")), "the beside-file was left behind")


class SlicingIsOneTransaction(unittest.TestCase):
    def test_two_lanes_slicing_at_once_keep_both_sets_of_pieces(self):
        """`slice_task` read under the lock and wrote outside it, so the later
        write carried a document read before the earlier one landed."""
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "backlog.yaml"
            path.write_text(yaml.safe_dump({"tasks": [
                {"id": "T1", "status": "todo", "needs": []},
                {"id": "T2", "status": "todo", "needs": []}]}))
            book = Backlog(path)
            # Every read dawdles before its write. Holding the lock, the second
            # lane cannot even read until the first has written, so both pieces
            # land; reading outside the lock, it reads the document the first
            # lane is about to replace and writes that one back, losing a piece.
            real_read = Backlog._read

            def slow_read(self):
                document = real_read(self)
                time.sleep(0.3)
                return document

            def slicing(task_id, label):
                book.slice_task(task_id, [{"goal": label, "files": [label]}])

            with unittest.mock.patch.object(Backlog, "_read", slow_read):
                hands = [threading.Thread(target=slicing, args=(t, f"piece-{t}")) for t in ("T1", "T2")]
                for hand in hands:
                    hand.start()
                for hand in hands:
                    hand.join(5)
            ids = {row["id"] for row in book.read()["tasks"]}
            self.assertIn("T1.1", ids)
            self.assertIn("T2.1", ids, "one lane's pieces were lost")


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
