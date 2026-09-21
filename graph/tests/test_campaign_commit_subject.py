"""Accepted task commits follow the repository's Conventional Commits rule."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaign_repo import git, repository
from keep import Keeper
from worktree import Worktree

EXPECTED_TESTS = 2


class CommitSubjectTest(unittest.TestCase):
    def test_a_card_id_does_not_replace_the_conventional_type(self):
        scratch, root = repository()
        self.addCleanup(scratch.cleanup)
        tree = Worktree(str(root), "rename-card").create(parent=scratch.name)
        self.addCleanup(tree.remove)
        (pathlib.Path(tree.path) / "pkg/a.py").write_text("accepted change\n")
        commit = Keeper(str(root), "campaign/test").keep(
            "rename-card", tree.path, "preserve a rename", files=["pkg/a.py"])
        subject = git(root, "show", "-s", "--format=%s", commit)
        self.assertRegex(subject, r"^(feat|fix|chore|docs|style|refactor|test|ci|build|perf|revert)(\(.+\))?: .+")
        self.assertIn("rename-card", subject)

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
