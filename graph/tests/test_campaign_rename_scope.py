"""Both endpoints of a rename must stay inside the card's grant."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaign_repo import git, repository
from worktree import Worktree
from worktree_scope import changed_outside

EXPECTED_TESTS = 5


class RenameScopeTest(unittest.TestCase):
    def setUp(self):
        scratch, root = repository()
        self.addCleanup(scratch.cleanup)
        self.tree = Worktree(str(root), "scope").create(parent=scratch.name)
        self.addCleanup(self.tree.remove)

    def test_a_directory_grant_does_not_authorize_an_outside_destination(self):
        git(self.tree.path, "mv", "pkg/a.py", "outside.py")
        self.assertTrue(changed_outside(self.tree.path, ["pkg"]),
                        "renaming out of the granted directory must be refused")

    def test_two_explicit_file_grants_authorize_their_rename(self):
        git(self.tree.path, "mv", "pkg/a.py", "pkg/b.py")
        self.assertEqual([], changed_outside(self.tree.path, ["pkg/a.py", "pkg/b.py"]))

    def test_a_destination_grant_does_not_authorize_an_outside_source(self):
        git(self.tree.path, "mv", "pkg/a.py", "outside.py")
        self.assertTrue(changed_outside(self.tree.path, ["outside.py"]))

    def test_an_in_directory_rename_remains_authorized(self):
        git(self.tree.path, "mv", "pkg/a.py", "pkg/b.py")
        self.assertEqual([], changed_outside(self.tree.path, ["pkg"]))

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
