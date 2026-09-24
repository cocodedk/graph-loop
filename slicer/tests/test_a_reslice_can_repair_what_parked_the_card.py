"""The refusal that made one parked card permanent.

A card was written granting only its test file while its gate asserted
behaviour that only the source file beside it could make true, so the card was
unbuildable and every re-slice of it was refused. The rule it hit is right and
declared (SLICER.md: a rewrite stays inside the failed card's file list, or the
original bad scope becomes permanent), and the escape it leaves — one separately
reviewed prerequisite atom — is legal. The planner spent all three rounds
without finding it (2026-09-18, the first real campaign run).

So the rule stays and its refusal names the answer, in this card's own file
names, the way the missing-atoms refusal already does.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from contracts import validate
from git_fixture import commit

EXPECTED_TESTS = 1


class OneLeafRewriteTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "specs").mkdir()
        (self.repo / "specs" / "a.md").write_text("# A\nOne claim.\n", "utf-8")
        for name in ("Fetcher.java", "FetchTest.java"):
            (self.repo / name).write_text("class X {}\n", "utf-8")
        commit(self.repo)

    def test_the_refusal_names_the_two_atoms_to_write(self):
        target = {"id": "old", "status": "needs_slice", "triage": "work",
                  "refused_why": "the builder wrote outside its files",
                  "goal": "the request names the app", "files": ["FetchTest.java"],
                  "gate": "set -e -o pipefail\nfalse", "done_when": "the test passes"}
        answer = {"result": "MOLECULE", "reason": "widen it", "molecule": {
            "name": "wider", "source": ["specs/a.md:2"], "goal": "the request names the app",
            "why": "the gate needs the fetcher", "needs": [], "atoms": [],
            "files": ["FetchTest.java", "Fetcher.java"],
            "gate": "set -e -o pipefail\nfalse", "done_when": "the test passes"}}
        with self.assertRaises(ValueError) as caught:
            validate(answer, repo=self.repo, sources=[self.repo / "specs"],
                     rows=[target], target=target)
        said = str(caught.exception)
        self.assertIn("Fetcher.java", said)              # the file it tried to add
        self.assertIn("FetchTest.java", said)            # the file the target grants
        self.assertIn("stage 1", said)
        self.assertIn("stage 2", said)


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
