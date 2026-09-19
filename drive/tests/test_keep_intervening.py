"""A keep never overwrites what another card kept in the same file.

Red first (round-2 finding 8): the keeper read the branch tip into a private
index and overlaid whole files from a checkout cut before the tip moved, so a
card that touched the same file as an earlier keep replaced it — the earlier
change vanished with no conflict and nothing to read. The work is merged from
the base the worktree was cut from instead: both changes survive when they are
in different places, and a real clash refuses the keep.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper
from test_keep import branch_files, repo, sha

EXPECTED_TESTS = 2


def cut(root: str, at: str, name: str) -> str:
    path = str(pathlib.Path(tempfile.mkdtemp()) / name)
    subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", path, at),
                   capture_output=True, check=True)
    return path


class InterveningKeepTest(unittest.TestCase):
    def setUp(self):
        self.root = repo()
        self.keeper = Keeper(self.root, "campaign/test")
        first = cut(self.root, self.keeper.tip(), "T0")
        (pathlib.Path(first) / "a.py").write_text("one\ntwo\nthree\n")
        self.keeper.keep("T0", first, "the file both cards will edit")
        self.shared = self.keeper.tip()   # both cards below are cut from here

    def _both(self, early_text: str, late_text: str) -> tuple[str, str]:
        early, late = cut(self.root, self.shared, "early"), cut(self.root, self.shared, "late")
        (pathlib.Path(early) / "a.py").write_text(early_text)
        (pathlib.Path(late) / "a.py").write_text(late_text)
        return early, late

    def test_a_later_keep_carries_the_earlier_keeps_change_to_the_same_file(self):
        early, late = self._both("ONE\ntwo\nthree\n", "one\ntwo\nTHREE\n")
        self.keeper.keep("T-early", early, "changed the first line", files=["a.py"])
        self.keeper.keep("T-late", late, "changed the last line", files=["a.py"])
        self.assertEqual("ONE\ntwo\nTHREE\n", branch_files(self.root, "campaign/test"))

    def test_two_cards_changing_the_same_line_refuse_instead_of_overwriting(self):
        early, late = self._both("ONE\ntwo\nthree\n", "uno\ntwo\nthree\n")
        self.keeper.keep("T-early", early, "changed the first line", files=["a.py"])
        stood = sha(self.root, "campaign/test")
        with self.assertRaises(RuntimeError) as caught:
            self.keeper.keep("T-late", late, "changed the first line too", files=["a.py"])
        self.assertIn("a.py", str(caught.exception))
        self.assertEqual(stood, sha(self.root, "campaign/test"))   # the branch did not move


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
