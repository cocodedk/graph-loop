"""Accepted coverage is a claim about molecules as much as about sources.

astra's review, finding 12: the coverage record digested the approved sources
alone, so a card deleted or rewritten after the review left the verdict
standing — the slicer went on answering "covered" about a backlog the reviewer
never saw. What is digested is what the reviewer read: `asking.index(rows)`.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import slicer_state
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 1


class CoverageCardsTest(unittest.TestCase):
    def test_a_card_removed_after_the_review_makes_the_coverage_stale(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        backlog, specs = repo / "backlog", repo / "specs"
        backlog.mkdir(); specs.mkdir()
        source = specs / "greeting.md"
        source.write_text("## Goal\nReturn a greeting.\n", "utf-8")
        rows = [{"id": "greeting", "status": "todo", "files": ["app.py"],
                 "goal": "return a greeting"}]

        slicer_state.close(backlog, [source], "accepted", repo, rows)
        self.assertTrue(slicer_state.covered(backlog, [source], repo, rows))
        self.assertFalse(slicer_state.covered(backlog, [source], repo, []))
        self.assertFalse((backlog / ".slicer-state.yaml").exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
