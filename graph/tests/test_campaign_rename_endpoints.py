"""Rename endpoints remain distinct, including exemptions and literal arrows."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaign_repo import git, repository
from worktree import Worktree
from worktree_scope import changed_outside

EXPECTED_TESTS = 7


class RenameEndpointsTest(unittest.TestCase):
    def rename(self, source, destination, grant):
        scratch, root = repository()
        self.addCleanup(scratch.cleanup)
        source_path = root / source
        if not source_path.exists():
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text("fixture\n")
            git(root, "add", "-f", "--", source)
            git(root, "commit", "-qm", "test: add endpoint fixture")
        tree = Worktree(str(root), "endpoints").create(parent=scratch.name)
        self.addCleanup(tree.remove)
        git(tree.path, "mv", "--", source, destination)
        return changed_outside(tree.path, grant)

    def test_literal_arrows_never_create_different_granted_endpoints(self):
        self.assertTrue(self.rename("owned -> secret", "dest", ["owned", "secret -> dest"]))

    def test_literal_arrows_stay_inside_their_granted_directory(self):
        self.assertEqual([], self.rename("pkg/a -> x.py", "pkg/b.py", ["pkg"]))

    def test_an_artifact_destination_cannot_hide_an_ungranted_source_deletion(self):
        self.assertTrue(self.rename("pkg/a.py", "outside.pyc", ["other.py"]))

    def test_an_artifact_source_cannot_authorize_an_ungranted_destination(self):
        self.assertTrue(self.rename("pkg/__pycache__/cached.py", "outside.py", ["pkg"]))

    def test_a_granted_source_can_be_renamed_to_an_exempt_artifact(self):
        self.assertEqual([], self.rename("pkg/a.py", "outside.pyc", ["pkg/a.py"]))

    def test_an_exempt_source_can_be_renamed_to_a_granted_destination(self):
        self.assertEqual([], self.rename("pkg/__pycache__/cached.py", "outside.py", ["outside.py"]))

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
