"""contracts._task's gate-output check against specific bypass attempts
Codex found across rounds 4-6: mktemp trust-boundary edge cases, nested
quote/heredoc parsing, and comment/command-position scanning.

Split out of test_contracts_gate_output.py at the 200-line cap: this is a
sibling, not a rewrite -- it shares no fixture with that file and needs
none of it.
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

EXPECTED_TESTS = 12


class GateOutputBypassTest(unittest.TestCase):
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

    def test_a_mktemp_template_argument_is_refused(self):
        # Codex round 4: a template can steer mktemp to create its file
        # inside the repository -- only the bare, argument-free form is trusted
        gate = 'OUT=$(mktemp ./gate.XXXXXX); tee "$OUT"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_quote_inside_a_nested_substitution_does_not_break_the_balance(self):
        # Codex round 4: the naive depth counter read the ")" inside the
        # single-quoted ')' as closing the substitution, hiding the real
        # redirect that follows it
        gate = "x=\"$(echo ')' > repo.out)\""
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_an_inline_mktemp_call_with_a_template_is_refused(self):
        # Codex round 5: the inline $(mktemp ...) form skipped the assignment
        # form's own argument check -- a template can steer it into the repo
        gate = 'cd simulation/tests/triage && pytest -q | tee "$(mktemp ./gate.XXXXXX)"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_tmp_path_that_walks_out_with_dotdot_is_refused(self):
        # Codex round 5: a literal prefix match let /tmp/../elsewhere/x
        # through because the text merely STARTS WITH "/tmp/"
        gate = ('cd simulation/tests/triage && pytest -q > '
                '"/tmp/../srv/projects/other-checkout/repo.out"')
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_an_escaped_backslash_before_a_closing_quote_is_not_mistaken_for_an_escaped_quote(self):
        # Codex round 5: skip_quote counted one backslash back, not a run --
        # "\\" is one escaped backslash, and the quote right after it closes
        gate = 'cd simulation/tests/triage && printf "\\\\" > repo.out'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_dev_null_with_trailing_shell_punctuation_stays_accepted(self):
        # regression: closing the /tmp/../ hole with an exact-equality
        # check for /dev/null broke the already-fixed `(... > /dev/null)`
        # shape, found by this round's own mandated 128-gate re-scan
        gate = "cd simulation/tests/triage && (pytest -q > /dev/null)"
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_ampersand_redirect_to_a_bare_filename_is_refused(self):
        # Codex round 6: >&word writes both streams to a real file unless
        # word is a bare descriptor number or "-" -- >&repo.out is a file
        gate = "cd simulation/tests/triage && pytest -q >&repo.out"
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_ampersand_redirect_with_a_space_to_a_bare_filename_is_refused(self):
        # the same operator, whitespace-separated from its target -- the
        # old capture read the bare "&" as the whole target and missed this
        gate = "cd simulation/tests/triage && pytest -q >& repo.out"
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_poisoned_tmpdir_before_a_bare_mktemp_is_refused(self):
        # Codex round 6: a bare $(mktemp) reads $TMPDIR -- TMPDIR=. steers
        # it into the current directory instead of the driver's own home
        gate = 'TMPDIR=. OUT=$(mktemp); tee "$OUT"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_a_directory_variable_suffix_with_dotdot_is_refused(self):
        # Codex round 6: $d is a genuinely trusted mktemp -d directory, but
        # its own suffix can still walk back out with a ".." segment
        gate = 'd=$(mktemp -d); tee "$d/../../repo-path"'
        with self.assertRaises(ValueError):
            self.check(gate)

    def test_tee_as_a_plain_word_argument_is_not_an_invocation(self):
        # Codex round 6: "tee" is only a command in command position -- as
        # grep's own search pattern it is just an argument
        gate = "cd simulation/tests/triage && grep -q tee app.py"
        self.assertEqual("MOLECULE", self.check(gate)["result"])

    def test_a_comment_containing_a_redirect_character_is_not_scanned(self):
        # Codex round 6: an unquoted # starts a comment bash never expands;
        # the > inside one is text, not an operator
        gate = "cd simulation/tests/triage && pytest -q  # a > b, not a redirect"
        self.assertEqual("MOLECULE", self.check(gate)["result"])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
