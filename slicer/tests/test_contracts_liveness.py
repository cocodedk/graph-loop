"""`contracts._task` refuses LIVE authority by reading the declared predicate,
not the raw `gate_has_side_effects` field.

Split out of test_contracts.py at the 200-line cap: this is a sibling, not a
rewrite — it shares no fixture with that file and needs none of it.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from contracts import validate

EXPECTED_TESTS = 1


class LiveAuthorityTest(unittest.TestCase):
    def test_the_live_authority_refusal_follows_the_declared_predicate(self):
        # Patched at the name contracts IMPORTED, not at its definition: before
        # this fixpoint the patch target does not exist, and that AttributeError
        # is itself the proof _task re-derived liveness from the raw field
        # instead of reading the shared predicate (test_backlog_status_live.py
        # patches every drive caller the same way).
        repo = pathlib.Path(tempfile.mkdtemp())
        (repo / "specs").mkdir()
        (repo / "specs" / "greeting.md").write_text("# Greeting\nA greeting is returned.\n", "utf-8")
        (repo / "app.py").write_text("present = True\n", "utf-8")
        answer = {"result": "MOLECULE", "reason": "one gap", "molecule": {
            "name": "greeting", "source": ["specs/greeting.md:2"],
            "goal": "return one greeting", "why": "the function is absent",
            "needs": [], "atoms": [], "files": ["app.py"],
            "gate": "set -e -o pipefail\npython3 -m unittest test_app.py",
            "done_when": "the greeting test passes"}}
        # gate_has_side_effects is unset above: only the patch says "live".
        with (unittest.mock.patch("contract_task.is_live", return_value=True),
              self.assertRaisesRegex(ValueError, "LIVE authority")):
            validate(answer, repo=repo, sources=[repo / "specs"], rows=[], target=None)


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
