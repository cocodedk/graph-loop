"""A builder-created symlink is committed as a symlink, not the target's
bytes, and a dangling one is not silently dropped. Split from `test_keep`
at the 200-line cap.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper
from test_keep import repo

EXPECTED_TESTS = 3


def ls_tree(root: str, branch: str, name: str) -> tuple[str, str]:
    """(mode, blob) for `name` as the kept commit's tree holds it."""
    line = subprocess.run(("git", "-C", root, "ls-tree", branch, "--", name),
                          capture_output=True, text=True, check=True).stdout.strip()
    mode, _, rest = line.split(" ", 2)
    blob = rest.split("\t", 1)[0]
    return mode, blob


def blob_text(root: str, blob: str) -> str:
    return subprocess.run(("git", "-C", root, "cat-file", "-p", blob),
                          capture_output=True, text=True, check=True).stdout


def blob_bytes(root: str, blob: str) -> bytes:
    """Raw stdout, undecoded — the text helper above would itself choke on a
    non-UTF-8 blob."""
    return subprocess.run(("git", "-C", root, "cat-file", "-p", blob),
                          capture_output=True, check=True).stdout


class SymlinkTest(unittest.TestCase):
    def setUp(self):
        self.root = repo()
        self.keeper = Keeper(self.root, "campaign/test")

    def _worktree(self, task_id: str) -> str:
        path = str(pathlib.Path(tempfile.mkdtemp()) / task_id)
        subprocess.run(("git", "-C", self.root, "worktree", "add", "-q", "--detach",
                        path, self.keeper.tip()), capture_output=True, check=True)
        return path

    def test_a_symlink_is_committed_as_a_symlink_not_the_targets_bytes(self):
        path = self._worktree("T1")
        (pathlib.Path(path) / "link").symlink_to("a.py")
        commit = self.keeper.keep("T1", path, "added a symlink")
        self.assertTrue(commit)
        mode, blob = ls_tree(self.root, "campaign/test", "link")
        self.assertEqual("120000", mode)
        self.assertEqual("a.py", blob_text(self.root, blob))

    def test_a_dangling_symlink_is_kept_as_a_symlink_to_its_missing_target(self):
        path = self._worktree("T1")
        (pathlib.Path(path) / "gone").symlink_to("nowhere")
        commit = self.keeper.keep("T1", path, "added a dangling symlink")
        self.assertTrue(commit)
        mode, blob = ls_tree(self.root, "campaign/test", "gone")
        self.assertEqual("120000", mode)
        self.assertEqual("nowhere", blob_text(self.root, blob))

    def test_a_non_utf8_symlink_target_is_kept_byte_for_byte(self):
        path = self._worktree("T1")
        target = pathlib.Path(path) / "raw"
        os.symlink(b"\xff", os.fsencode(target))
        commit = self.keeper.keep("T1", path, "added a non-utf8 symlink")
        self.assertTrue(commit)
        mode, blob = ls_tree(self.root, "campaign/test", "raw")
        self.assertEqual("120000", mode)
        self.assertEqual(b"\xff", blob_bytes(self.root, blob))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
