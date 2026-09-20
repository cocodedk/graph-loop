"""A coverage record about a source that is gone goes with it.

Codex's review: `main` validates its approved sources before anything else and
exits 2, so the record it once wrote for that source was never read and never
dropped. The slicer owns that record, and a claim about a file nobody can read
is not one it may keep.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import slicer_state
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

import slicer

EXPECTED_TESTS = 1


class MissingSourceTest(unittest.TestCase):
    def test_a_deleted_approved_source_takes_its_coverage_record_with_it(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        backlog, specs = repo / "backlog", repo / "specs"
        backlog.mkdir(); specs.mkdir()
        source = specs / "greeting.md"
        source.write_text("## Goal\nReturn a greeting.\n", "utf-8")
        slicer_state.close(backlog, [source], "accepted", repo, [])
        source.unlink()

        with mock.patch.object(slicer, "ask") as ask:
            result = slicer.main(["--repo", str(repo), "--backlog", str(backlog),
                                  "--source", "specs/greeting.md"])

        self.assertEqual(2, result)
        ask.assert_not_called()          # refused before any model call, as it was
        self.assertFalse((backlog / slicer_state.STATE).exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
