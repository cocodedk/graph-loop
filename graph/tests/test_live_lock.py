"""What a crashed writer never gets to publish, and what an empty lock means.

Two defects GLM M18 found on 2026-09-02: `take` wrote its record straight
into the lock file, so a reader mid-write could see it torn; and an empty
lock file -- nobody managed to write a holder into it -- stays held until a
person clears it, never read as free. Companion to the take/holder/give_back
coverage in test_worktree.py.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from worktree import LiveLock

EXPECTED_TESTS = 4


class AtomicPublishTest(unittest.TestCase):
    def test_a_crash_before_the_record_is_complete_leaves_no_lock_at_all(self):
        """A crash mid-write leaves a torn record in the temp file, never in
        the published lock: `write_text` here writes half the record to
        disk, then raises, standing in for a process cut off after open but
        before its content is whole."""
        lock = LiveLock(tempfile.mkdtemp())
        written: list[pathlib.Path] = []

        def torn(path, data, encoding=None):
            written.append(path)
            path.write_bytes(data[: len(data) // 2].encode(encoding or "utf-8"))
            raise OSError("killed mid-write")

        with (unittest.mock.patch.object(pathlib.Path, "write_text", autospec=True,
                                         side_effect=torn),
              self.assertRaises(OSError)):
            lock.take("T1")
        self.assertFalse(lock.path.exists())
        self.assertFalse(written[0].exists())      # the torn temp file is gone too


class EmptyLockTest(unittest.TestCase):
    def test_an_empty_lock_file_is_held_not_free(self):
        """Empty does not prove no living owner: the old writer creates the
        lock before it writes the holder in."""
        folder = tempfile.mkdtemp()
        (pathlib.Path(folder) / "live-stack.lock").touch()
        self.assertFalse(LiveLock(folder).holder_is_gone())

    def test_an_unparseable_non_empty_lock_file_is_held_not_free(self):
        folder = tempfile.mkdtemp()
        (pathlib.Path(folder) / "live-stack.lock").write_text("garbage", "utf-8")
        self.assertFalse(LiveLock(folder).holder_is_gone())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
