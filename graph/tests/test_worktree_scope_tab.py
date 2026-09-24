"""A gitlink whose name has a tab in it: both `ls-tree`'s and `ls-files
--stage`'s records are `<mode> ...` TAB `<path>`, so a tab inside the path
itself must never be mistaken for that separator. Split out of
`test_worktree_scope` at the 200-line cap; that file stays the front door."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from worktree_scope import _gitlinks, changed_outside

EXPECTED_TESTS = 2


class GitlinkTabNameTest(unittest.TestCase):
    def test_an_owned_gitlink_with_a_tab_in_its_name_admits_no_sibling(self):
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "pkg").mkdir()
        inner = tree / "pkg" / "weird\tname"
        inner.mkdir()
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=inner, capture_output=True, check=True)
        (inner / "x.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=inner, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "inner"), cwd=inner, capture_output=True, check=True)
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)   # stages the gitlink
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "pkg" / "sibling.py").write_text("two\n")     # a new file beside the owned gitlink
        self.assertIn("pkg/sibling.py", changed_outside(str(tree), ["pkg/weird\tname"], may_add=True))

    def test_a_staged_gitlink_with_a_tab_in_its_name_is_listed_by_gitlinks(self):
        # `ls-files --stage` without `-z` C-quotes the tab: the quoted string
        # never equals the real path, so the staged gitlink goes unseen.
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "pkg").mkdir()
        inner = tree / "pkg" / "weird\tname"
        inner.mkdir()
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=inner, capture_output=True, check=True)
        (inner / "x.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=inner, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "inner"), cwd=inner, capture_output=True, check=True)
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)   # stages the gitlink
        self.assertIn("pkg/weird\tname", _gitlinks(str(tree)))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
