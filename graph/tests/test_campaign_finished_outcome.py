"""A settled result keeps the meaning of its worktree field."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from loop_start import already_finished

EXPECTED_TESTS = 3


class FinishedOutcomeTest(unittest.TestCase):
    def test_existing_worktree_metadata_is_preserved(self):
        task = {"status": "done", "commit": "accepted-commit", "worktree": "accepted-tree"}
        result = already_finished(task)
        self.assertEqual("done", result.state)
        self.assertEqual("accepted-tree", result.worktree)
        self.assertEqual("accepted-commit", task["commit"])

    def test_a_commit_is_never_invented_as_a_worktree(self):
        result = already_finished({"status": "done", "commit": "accepted-commit"})
        self.assertEqual("", result.worktree)

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
