"""An owned file whose name has a space in it: `git status --porcelain`
without `-z` wraps such a path in quotes, so the quoted string never equals
the owned path and an in-scope edit reads as outside it. Split out of
`test_worktree_scope` at the 200-line cap; that file stays the front door."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from worktree_scope import changed_outside

EXPECTED_TESTS = 1


class OwnedFileSpaceNameTest(unittest.TestCase):
    def test_an_owned_file_with_a_space_in_its_name_edited_is_not_outside(self):
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "pkg").mkdir()
        (tree / "pkg" / "weird name.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "pkg" / "weird name.py").write_text("two\n")   # the builder's own edit
        self.assertEqual([], changed_outside(str(tree), ["pkg/weird name.py"]))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
