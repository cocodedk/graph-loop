"""A published rename is the same deletion and addition the reviewer saw."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaign_repo import git, repository
from keep import Keeper
from worktree import Worktree

EXPECTED_TESTS = 2


class RenamePublicationTest(unittest.TestCase):
    def test_a_published_rename_removes_its_original(self):
        scratch, root = repository()
        self.addCleanup(scratch.cleanup)
        tree = Worktree(str(root), "rename").create(parent=scratch.name)
        self.addCleanup(tree.remove)
        git(tree.path, "mv", "pkg/a.py", "pkg/b.py")
        commit = Keeper(str(root), "campaign/test").keep(
            "rename", tree.path, "rename the module", files=["pkg"])
        paths = git(root, "ls-tree", "-r", "--name-only", commit).splitlines()
        self.assertNotIn("pkg/a.py", paths, "a published rename must remove its source")
        self.assertIn("pkg/b.py", paths)
        self.assertIn("pkg/stays.py", paths)
        self.assertEqual("original content", git(root, "show", f"{commit}:pkg/b.py"))

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
