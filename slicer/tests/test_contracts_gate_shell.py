"""`contracts._task` refuses a gate through the shared `has_pipefail_header`
predicate, not by re-reading the gate text itself.

Split out as a sibling of test_contracts.py at the 200-line cap. The
predicate's own cases (exact header, semicolon-joined, leading comment,
split across two lines, reordered flags) live where the predicate lives,
`drive/tests/test_gate_shell.py` -- this file only proves
`_task` defers to it, the same way test_contracts_liveness.py proves
`_task` defers to `is_live` rather than re-deriving it.
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

EXPECTED_TESTS = 2


class GateShellHeaderTest(unittest.TestCase):
    def test_the_refusal_follows_the_shared_predicate(self):
        # Patched at the name contracts IMPORTED: the gate below is a
        # genuinely compliant header, so the only reason this is refused is
        # that _task asked the shared predicate and got told no.
        repo = pathlib.Path(tempfile.mkdtemp())
        (repo / "specs").mkdir()
        (repo / "specs" / "greeting.md").write_text(
            "# Greeting\nA greeting is returned.\n", "utf-8")
        (repo / "app.py").write_text("present = True\n", "utf-8")
        answer = {"result": "MOLECULE", "reason": "one gap", "molecule": {
            "name": "greeting", "source": ["specs/greeting.md:2"],
            "goal": "return one greeting", "why": "the function is absent",
            "needs": [], "atoms": [], "files": ["app.py"],
            "gate": "set -e -o pipefail\npytest -q",
            "done_when": "the greeting test passes"}}
        with (unittest.mock.patch("contract_task.has_pipefail_header", return_value=False),
              self.assertRaisesRegex(ValueError, "set -e -o pipefail")):
            validate(answer, repo=repo, sources=[repo / "specs"], rows=[], target=None)


class PinsACountTest(unittest.TestCase):
    def test_a_gate_that_pins_expected_is_refused_with_the_fragment(self):
        # Same pattern as GateShellHeaderTest above: the gate is otherwise
        # compliant, so the only reason this is refused is that _task asked
        # the shared predicate and got told EXPECTED is pinned to a count
        # (a lesson of 2026-09-03: EXPECTED moves as tests land). The gate
        # must mention a run_all module (round 6, finding 1) for the check
        # to run at all.
        repo = pathlib.Path(tempfile.mkdtemp())
        (repo / "specs").mkdir()
        (repo / "specs" / "greeting.md").write_text(
            "# Greeting\nA greeting is returned.\n", "utf-8")
        (repo / "app.py").write_text("present = True\n", "utf-8")
        answer = {"result": "MOLECULE", "reason": "one gap", "molecule": {
            "name": "greeting", "source": ["specs/greeting.md:2"],
            "goal": "return one greeting", "why": "the function is absent",
            "needs": [], "atoms": [], "files": ["app.py"],
            "gate": "set -e -o pipefail\npython3 -c \"assert EXPECTED == 15\" # run_all.py",
            "done_when": "the greeting test passes"}}
        with self.assertRaisesRegex(ValueError, "the gate pins EXPECTED to 15"):
            validate(answer, repo=repo, sources=[repo / "specs"], rows=[], target=None)


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
