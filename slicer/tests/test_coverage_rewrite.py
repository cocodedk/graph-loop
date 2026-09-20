"""A card rewritten to promise less no longer reads as covered.

Codex's review of the finding-12 brick, point 2: the coverage record digested
`asking.index`, one line per card — id, status, files and the goal's first
line. Rewriting a card's `gate` and `done_when` changed nothing that was
hashed, so an accepted verdict stood over a card that now proves something
else. Companion to test_coverage_cards.py, which covers a card removed.
"""

from __future__ import annotations

import copy
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import slicer_state
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 1

REVIEWED = [{"id": "greeting", "status": "todo", "files": ["app.py"],
             "goal": "return a greeting",
             "gate": "set -e -o pipefail\npython3 -m unittest tests.test_greeting",
             "done_when": "the greeting test passes"}]


class RewriteTest(unittest.TestCase):
    def test_a_rewritten_gate_and_done_when_make_the_coverage_stale(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        backlog, specs = repo / "backlog", repo / "specs"
        backlog.mkdir(); specs.mkdir()
        source = specs / "greeting.md"
        source.write_text("## Goal\nReturn a greeting.\n", "utf-8")

        slicer_state.close(backlog, [source], "accepted", repo, REVIEWED)
        self.assertTrue(slicer_state.covered(backlog, [source], repo, REVIEWED))

        weakened = copy.deepcopy(REVIEWED)
        weakened[0]["gate"] = "set -e -o pipefail\ntrue"
        weakened[0]["done_when"] = "nothing in particular"
        self.assertFalse(slicer_state.covered(backlog, [source], repo, weakened))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
