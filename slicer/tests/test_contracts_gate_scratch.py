"""A gate's scratch goes where the driver can remove it: under the TMPDIR the
driver points at the gate's own home (`gate_sandbox.environment`, and
`run_gate` removes that home in its finally), never into the host's /tmp.

Sibling of test_contracts_gate_output.py, which holds the repo-safety rules.
This file holds the rule about WHICH scratch root is trusted: what a gate
pinned to literal /tmp was never removed, and files like those filled the disk
on 2026-09-03 and killed every process on the host.
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

EXPECTED_TESTS = 6


class GateScratchTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "specs").mkdir()
        (self.repo / "specs" / "greeting.md").write_text(
            "# Greeting\nA greeting is returned.\n", "utf-8")
        (self.repo / "app.py").write_text("present = True\n", "utf-8")
        commit(self.repo)

    def check(self, gate: str) -> dict:
        atom = {"result": "MOLECULE", "reason": "one gap", "molecule": {
            "name": "greeting", "source": ["specs/greeting.md:2"],
            "goal": "return one greeting", "why": "the function is absent",
            "needs": [], "atoms": [], "files": ["app.py"],
            "gate": "set -e -o pipefail\n" + gate,
            "done_when": "the greeting test passes"}}
        return validate(atom, repo=self.repo, sources=[self.repo / "specs"],
                        rows=[], target=None)

    def test_a_gate_writing_under_tmpdir_is_accepted(self):
        gate = 'pytest -q | tee "$TMPDIR/out" | tail -3'
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_the_braced_spelling_of_tmpdir_is_accepted_too(self):
        gate = 'pytest -q > "${TMPDIR}/out"'
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_a_bare_mktemp_is_accepted(self):
        # bare mktemp follows TMPDIR: the gate home under the driver, and /tmp
        # in the builder's own shell, where TMPDIR is unset
        gate = 'OUT=$(mktemp) && pytest -q | tee "$OUT" | tail -3'
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_a_gate_that_points_tmpdir_at_the_repository_is_refused(self):
        # Codex: the assignment scan skips a name's own mktemp call, so an
        # untrusted `TMPDIR=$(mktemp -d ./x)` was not counted as assigning
        # TMPDIR and every "$TMPDIR/..." write below it landed in the repo
        gate = 'TMPDIR=$(mktemp -d ./leak.XXXXXX); echo proof > "$TMPDIR/out"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_gate_that_assigns_tmpdir_from_a_trusted_mktemp_is_refused_too(self):
        # the same hole through the OTHER branch: a trusted call still moves
        # the root, and this scan cannot see which line ran first
        gate = 'TMPDIR=$(mktemp -d); pytest -q > "$TMPDIR/out"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_gate_writing_into_literal_tmp_is_refused(self):
        # the host's /tmp outlives the gate: nothing removes what lands there
        gate = "pytest -q | tee /tmp/out | tail -3"
        with self.assertRaises(ValueError) as caught:
            self.check(gate)
        self.assertIn("/tmp/out", str(caught.exception))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
