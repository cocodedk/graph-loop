"""A full disk must not turn a stop into a crash (issue #260).

A green, accepted feature whose commit could not be made on a full disk stops, and the stop path
leaves a note in the kept tree. When that write fails too, the stop must still be recorded: the
event, the mail and the spec's front matter, so a rerun carries on in the kept tree instead of
rebuilding. Git is real; the rest is faked (`test_lean_run.Rig`).
"""

import errno
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_git
from test_lean_run import Rig
from worktree import KEEP_NOTE

EXPECTED_TESTS = 2
FULL = "git add: fatal: unable to write new index file: No space left on device"
real_write = pathlib.Path.write_text


def write_unless_note(self, *args, **kwargs):
    if self.name == KEEP_NOTE:
        raise OSError(errno.EDQUOT, "Disk quota exceeded")
    return real_write(self, *args, **kwargs)


class FullDisk(Rig):
    def stop_on_a_full_disk(self):
        with mock.patch.object(lean_git, "publish", side_effect=RuntimeError(FULL)), \
                mock.patch.object(pathlib.Path, "write_text", write_unless_note):
            return self.run_it(self.builder(("ring.py", "amber\n")))

    def test_the_stop_is_recorded_when_the_note_cannot_be_written(self):
        self.assertEqual("", self.stop_on_a_full_disk())
        stopped = next(row for row in self.ws.events() if row["kind"] == "lean_stopped")
        self.assertIn("No space left on device", stopped["why"])
        self.assertEqual(1, len(self.mails))
        self.assertIn("No space left on device", self.mails[0][1])
        self.assertIn("lean_status: stopped", self.spec.read_text())

    def test_the_accepted_work_is_kept_for_the_next_run(self):
        self.stop_on_a_full_disk()
        kept = next(row for row in self.ws.events() if row["kind"] == "lean_stopped")["tree"]
        self.assertEqual("amber\n", (pathlib.Path(kept) / "ring.py").read_text())
        self.assertIn(f"lean_worktree: {kept}", self.spec.read_text())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the two above and this one


if __name__ == "__main__":
    unittest.main()
