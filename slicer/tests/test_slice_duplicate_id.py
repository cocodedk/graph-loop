"""An atom's published id is the whole id, and it must be new.

astra's review, finding 11: only the molecule's own name was compared with the
backlog. An atom's id is derived from where it sits — `molecule.atom`
(`backlog_tree.read`) — so a molecule `greeting` with an atom `reader` claims
`greeting.reader`, which a molecule cut into its own folder may already own.
SLICER.md:171-173 requires every published id to be unique.
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


class DuplicateFullIdTest(unittest.TestCase):
    def test_an_atom_may_not_claim_an_id_the_backlog_already_holds(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        (repo / "specs").mkdir()
        (repo / "specs" / "greeting.md").write_text("# Greeting\nA greeting is returned.\n", "utf-8")
        (repo / "app.py").write_text("present = True\n", "utf-8")
        rows = [{"id": "greeting.reader", "status": "todo", "needs": [], "files": ["app.py"],
                 "goal": "read the greeting"}]
        answer = {"result": "MOLECULE", "reason": "one gap", "molecule": {
            "name": "greeting", "source": ["specs/greeting.md:2"], "goal": "return a greeting",
            "why": "the function is absent", "needs": [], "atoms": [
                {"name": "reader", "stage": 1, "goal": "read it", "files": ["app.py"],
                 "gate": "set -e -o pipefail\nfalse", "done_when": "the reader test passes"}]}}
        with self.assertRaisesRegex(ValueError, "greeting.reader already exists"):
            validate(answer, repo=repo, sources=[repo / "specs"], rows=rows)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
