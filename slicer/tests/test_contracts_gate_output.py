"""`contracts._task` refuses a gate that tees or redirects into a file inside
the repository it judges.

Split out as a sibling of test_contracts.py at the 200-line cap: this is the
regression for the defect that cost a 20-minute build (2026-09-03) — a
published gate teed into a bare filename and the graph loop's own lane guard
caught the fault only after the build was paid for.
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

EXPECTED_TESTS = 16


class GateOutputTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "specs").mkdir()
        (self.repo / "specs" / "greeting.md").write_text(
            "# Greeting\nA greeting is returned.\n", "utf-8")
        (self.repo / "app.py").write_text("present = True\n", "utf-8")
        commit(self.repo)

    def atom(self, gate: str) -> dict:
        # every gate here is prefixed with the required header so each test
        # still exercises the sink check alone, not the header check too
        return {"result": "MOLECULE", "reason": "one gap", "molecule": {
            "name": "greeting", "source": ["specs/greeting.md:2"],
            "goal": "return one greeting", "why": "the function is absent",
            "needs": [], "atoms": [], "files": ["app.py"],
            "gate": "set -e -o pipefail\n" + gate,
            "done_when": "the greeting test passes"}}

    def check(self, gate: str) -> dict:
        return validate(self.atom(gate), repo=self.repo,
                        sources=[self.repo / "specs"], rows=[], target=None)

    def test_a_gate_that_tees_into_a_relative_path_is_refused(self):
        # the real defect gate (2026-09-03): its fd-dup (2>&1), its /dev/null
        # and its bad tee all fire in the one pipeline this reruns verbatim
        gate = ("(cd simulation/tests/triage && timeout 900 "
                "../../.venv/bin/python3 -m unittest test_zone_claim 2>&1 "
                "1>/dev/null | tee zone-claim.out | tail -3 | grep -qx 'OK')")
        with self.assertRaises(ValueError) as caught:
            self.check(gate)
        self.assertIn("zone-claim.out", str(caught.exception))
        self.assertIn("$(mktemp)", str(caught.exception))

    def test_the_same_gate_piped_through_mktemp_is_accepted(self):
        gate = ('cd simulation/tests/triage && OUT=$(mktemp) && '
                'pytest -q | tee "$OUT" | tail -3')
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_dev_null_and_an_fd_merge_are_accepted(self):
        gate = "cd simulation/tests/triage && pytest -q > /dev/null 2>&1"
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_awk_and_sql_comparisons_are_not_mistaken_for_a_redirect(self):
        # a scan of every real gate in the repo (2026-09-03) found the naive
        # form of this check also matching SQL's ->> and awk's >=, neither a
        # file write: >= is a comparison and -> / ->> is never a redirect
        gate = ("psql -tAc \"select 1 from t where targets->>0 = 'x'\" "
                "> /dev/null && pytest -q 2>&1 | tail -5 | "
                "awk '/^Ran/{n=$2} /^OK/{ok=1} END{exit !(ok && n>=4)}'")
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_a_mktemp_directory_used_as_a_tee_target_is_accepted(self):
        # this codebase's own mutation-testing gates route a sed rewrite
        # through a mktemp -d directory before diffing it against the source
        gate = 'd=$(mktemp -d) && sed "s/x/y/" app.py > "$d/mutant.py"'
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_quoting_the_mktemp_assignment_is_still_a_mktemp_assignment(self):
        """`WORK="$(mktemp -d)"` is what the slicer writes and what a careful
        shell author writes, and there was no allowance for the quote between
        `=` and `$(`. So the name fell through to the bare-assignment scan,
        became untrusted, and the gate was refused for writing somewhere
        nothing owns — with a message saying to use `$(mktemp)`, which is
        exactly what it already did. Three repair rounds could not act on that,
        so the card parked twice on the identical sentence (2026-09-18)."""
        for gate in ('WORK="$(mktemp -d)"\ncat app.py > "$WORK/Check.java"',
                     "WORK='$(mktemp -d)'\ncat app.py > \"$WORK/Check.java\"",
                     'WORK=$(mktemp -d)\ncat app.py > "$WORK/Check.java"'):
            with self.subTest(gate=gate.splitlines()[0]):
                self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_a_refusal_names_the_variable_it_does_not_trust(self):
        """A refusal that restates a rule the gate already follows cannot drive
        a repair, and the round is spent for nothing."""
        with self.assertRaises(ValueError) as caught:
            self.check('OUT=zone-claim.out\ncat app.py > "$OUT"')
        said = str(caught.exception)
        self.assertIn("$OUT", said)
        self.assertIn("was not assigned from `mktemp`", said)   # the actual reason

    def test_a_variable_never_assigned_from_mktemp_is_refused(self):
        # Codex round 2: a $VAR-shaped target is only safe when THIS gate
        # assigned that name from mktemp -- not merely because it looks like
        # "$OUT". Here OUT is a bare relative filename wearing a variable's
        # clothes.
        gate = 'OUT=zone-claim.out; tee "$OUT"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_pwd_prefixed_target_is_refused(self):
        # $PWD is a real shell variable, but never one this gate assigned
        # from mktemp -- it resolves inside the repository the gate runs in
        gate = 'cd simulation/tests/triage && pytest -q > "$PWD/out"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_quoted_comparison_inside_python_c_is_accepted(self):
        # Codex round 2: the > here is a Python comparison living inside a
        # single-quoted -c argument, never a shell operator at all
        gate = "python3 -c 'assert 2 > 1'"
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_the_clobber_operator_is_refused(self):
        # >| forces a write even under noclobber -- the naive regex read
        # its own "|" as the target and missed the real one behind it
        gate = "cd simulation/tests/triage && pytest -q >| zone-claim.out"
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_single_quoted_mktemp_call_is_a_literal_filename_refused(self):
        # Codex round 3: single quotes make $(mktemp ...) a literal filename,
        # never a real call, even for the otherwise-trusted bare form --
        gate = "cd simulation/tests/triage && pytest -q | tee '$(mktemp)'"
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_redirect_on_a_heredocs_own_header_line_is_refused(self):
        # Codex round 3: the mask used to start at the delimiter itself,
        # swallowing the header line's own redirect along with the body
        gate = "cat <<EOF > repo.out\nhello\nEOF"
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_command_substitution_inside_double_quotes_is_scanned(self):
        # Codex round 3: bash still executes $(...) inside "..." -- masking
        # the whole quoted string hid a real tee from the scan
        gate = 'x="$(tee repo.out)"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_command_substitution_inside_an_unquoted_heredoc_is_scanned(self):
        # an unquoted heredoc delimiter (<<EOF, not <<'EOF') still expands
        # $(...) inside its body
        gate = "cat <<EOF\n$(echo hi > repo.out)\nEOF"
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_every_tee_operand_is_checked_not_just_the_first(self):
        # Codex round 4: tee can write to several files at once -- checking
        # only the first operand let a second, bare one through unseen
        gate = ('cd simulation/tests/triage && pytest -q | '
                'tee "$(mktemp)" repo.out')
        with self.assertRaises(ValueError):
            self.check(gate)


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
