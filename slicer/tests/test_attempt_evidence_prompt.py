"""Attempt evidence must not masquerade as work on the campaign branch."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — shared temporary root, removed at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from asking import prompt


class AttemptEvidenceTest(unittest.TestCase):
    def test_attempt_paths_and_diffs_are_not_the_completion_baseline(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        source = repo / "goal.md"
        source.write_text("Implement the behaviour.\n")
        text = prompt(repo, [source], [], target={"id": "T1", "worktree": "attempt"})
        self.assertIn("worktree/rebuild_from paths and attempt diffs are unlanded builder work", text)
        self.assertIn("Read the campaign tip here to decide what is already complete", text)
        self.assertIn("never use an attempt worktree as the repository baseline", text)


if __name__ == "__main__":
    unittest.main()
