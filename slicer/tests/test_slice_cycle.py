"""A published slice may not wait on the leaf it replaces.

astra's review, finding 11: an atom could name its own replaced parent. The
tree then reads `old` waiting for `smaller`, `smaller` waiting for
`smaller.first`, and `smaller.first` waiting for `old` — three cards that can
never become ready, because `Backlog.ready` only offers a card whose whole
`needs` has settled. SLICER.md:253 requires the order to have no cycle.
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

EXPECTED_TESTS = 1


class SliceCycleTest(unittest.TestCase):
    def test_an_atom_that_waits_on_its_replaced_parent_is_refused(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        (repo / "specs").mkdir()
        (repo / "specs" / "greeting.md").write_text("# Greeting\nA greeting is returned.\n", "utf-8")
        (repo / "app.py").write_text("present = True\n", "utf-8")
        target = {"id": "old", "goal": "work", "files": ["app.py"], "needs": [],
                  "gate": "set -e -o pipefail\nfalse", "done_when": "proof",
                  "status": "needs_slice", "triage": "work"}
        answer = {"result": "MOLECULE", "reason": "the wall was too broad", "molecule": {
            "name": "smaller", "source": ["specs/greeting.md:2"], "goal": "narrow work",
            "why": "the gate was too broad", "needs": [], "atoms": [
                {"name": "first", "stage": 1, "goal": "one narrow step", "files": ["app.py"],
                 "gate": "set -e -o pipefail\nfalse", "done_when": "the step proves it",
                 "needs": ["old"]}]}}
        with self.assertRaisesRegex(ValueError, "circle"):
            validate(answer, repo=repo, sources=[repo / "specs"], rows=[target], target=target)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
