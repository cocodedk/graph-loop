"""`has_pipefail_header` is the one declared predicate for "does this gate's
first line turn on -e and pipefail" -- read by the slicer's `contracts.py`
the way `is_live` and `gate_files` are, never re-derived at the call site.

The planner kept writing multi-step gates as a same-line
`set -o pipefail; (a) && (b) && (c ; d)` chain or bare newline-separated
commands, and the reviewer refused them before a person decided
(2026-09-03). The parser demands exactly the text the
planner prompt and BLUEPRINT.md ask for: no blank or comment line first, no
split across two lines, no reordered flags -- a tolerant reading of any of
those let the planner keep guessing at a shape that then failed review anyway.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from gate_shell import has_pipefail_header, pins_a_count

EXPECTED_TESTS = 26
RUNNER = "run_all.py; "  # satisfies the round 6 scoping guard


class HasPipefailHeaderTest(unittest.TestCase):
    def test_the_exact_header_alone_is_accepted(self):
        self.assertTrue(has_pipefail_header("set -e -o pipefail"))

    def test_the_header_first_then_more_content_is_accepted(self):
        gate = "set -e -o pipefail\n(echo a) && (echo b) && (echo c ; echo d)"
        self.assertTrue(has_pipefail_header(gate))

    def test_a_leading_blank_line_is_refused(self):
        # the rule is the exact FIRST line, not the first non-empty one --
        # a blank line before the header is refused like anything else there
        self.assertFalse(has_pipefail_header("\nset -e -o pipefail\npytest -q"))

    def test_a_semicolon_joined_pipefail_chain_is_refused(self):
        # the real defect shape (2026-09-03): joined by `;` to the rest of
        # the line, missing -e -- an earlier failure can pass silently
        gate = "set -o pipefail; (echo a) && (echo b) && (echo c ; echo d)"
        self.assertFalse(has_pipefail_header(gate))

    def test_a_leading_comment_line_is_refused(self):
        # the parser no longer tolerates what the prompt does not ask for
        self.assertFalse(has_pipefail_header("# comment\nset -e -o pipefail\npytest -q"))

    def test_the_two_line_split_is_refused(self):
        # set -o pipefail / set -e on separate lines used to be accepted;
        # the prompt asks for one exact line, so the parser now demands it
        self.assertFalse(has_pipefail_header("set -o pipefail\nset -e\npytest -q"))

    def test_reversed_flags_on_one_line_are_refused(self):
        self.assertFalse(has_pipefail_header("set -o pipefail -e\npytest -q"))


class PinsACountTest(unittest.TestCase):
    # The real defect, 2026-09-03: "the triage runner counts
    # its own test cases (EXPECTED), so a card gate that restated the count
    # -- first as a literal, then as len(MODULES) -- broke the moment a
    # module held two tests". Three spellings of EXPECTED pinned to a count
    # are refused; a comparison to another read value is fine. The check is
    # scoped to gates that mention a runner module (round 6, finding 1:
    # every run_all.py -- triage, verifier, journal -- declares MODULES and
    # EXPECTED the same way; an unrelated EXPECTED elsewhere is fine), so
    # every fixture below mentions RUNNER.
    def test_the_bare_name_pinned_to_a_literal_returns_the_literal(self):
        self.assertEqual("15", pins_a_count(RUNNER + "python3 -c \"assert EXPECTED == 15\""))

    def test_the_dotted_value_spelling_pinned_to_a_literal_returns_it(self):
        self.assertEqual("8", pins_a_count(RUNNER + "assert expected.value == 8"))

    def test_the_bracket_spelling_pinned_to_len_returns_the_len_call(self):
        gate = RUNNER + 'assert data["EXPECTED"] == len(MODULES)'
        self.assertEqual("len(MODULES)", pins_a_count(gate))

    def test_expected_compared_to_a_value_read_from_head_is_refused(self):
        # Codex round 5, finding 1: this form was blessed once, as "HEAD's
        # value plus this card's own tests" -- and it broke the day it
        # landed. The keeper re-runs a gate after committing the work, so
        # by the second run HEAD already holds what the gate calls new,
        # and the comparison is never true again. `old` is traced as an
        # alias the same way an EXPECTED lookup is.
        gate = (RUNNER + 'old=int(subprocess.check_output(["git","show","HEAD:count.txt"])); '
                'assert EXPECTED == old + 1')
        self.assertEqual("old", pins_a_count(gate))

    def test_expected_compared_to_what_the_runner_collects_is_fine(self):
        self.assertIsNone(pins_a_count(RUNNER + "assert EXPECTED == suite.countTestCases()"))

    def test_reversed_literal_operand_is_also_refused(self):
        # Codex round 2, finding 3: the two sides of `==` are interchangeable
        self.assertEqual("15", pins_a_count(RUNNER + "assert 15 == EXPECTED"))

    def test_reversed_len_operand_is_also_refused(self):
        self.assertEqual("len(MODULES)", pins_a_count(RUNNER + "assert len(MODULES) == EXPECTED"))

    def test_an_ast_walk_alias_bound_from_the_expected_lookup_is_refused(self):
        # Codex round 2, finding 1: the recorded case never writes the word
        # EXPECTED next to `==` -- it binds the ast node to the alias `e`
        # two statements earlier (`e=A(R,'EXPECTED')`) and pins
        # `e.value==14`. Inlined verbatim (not read from the live molecule
        # file at test time): that card can be requeued and its gate
        # rewritten, which would break this test with gate_shell.py
        # untouched (a card of the first campaign,
        # triage-clock-seam-instant/molecule.md:57-58, the two asserted
        # statements, plus the run_all.py open() one line earlier so the
        # round 6 scoping guard sees it).
        gate = ("R=ast.parse(open('run_all.py').read()); "
                "e=A(R,'EXPECTED'); assert isinstance(e,ast.Constant), "
                "'EXPECTED is not a literal number'; "
                "assert e.value==14, 'EXPECTED is not 14 (the 13 tests "
                "collected today plus this module one test)'")
        self.assertEqual("14", pins_a_count(gate))

    def test_bind_then_compare_then_reassign_is_still_a_real_pin(self):
        # Codex round 4, finding 2: the comparison happens before the
        # later, unrelated reassignment -- order-blind tracking (a static
        # last-assignment-wins set) would miss this.
        gate = RUNNER + "e=A(R,'EXPECTED'); assert e.value==15; e=42"
        self.assertEqual("15", pins_a_count(gate))

    def test_compare_then_bind_is_not_a_pin(self):
        # The alias is bound to EXPECTED only AFTER the comparison ran, so
        # the comparison read something unrelated -- order-blind tracking
        # (a static assigned-anywhere set) would wrongly refuse this.
        gate = RUNNER + "e=99; assert e.value==15; e=A(R,'EXPECTED')"
        self.assertIsNone(pins_a_count(gate))

    def test_a_whole_program_inside_one_dash_c_string_is_still_read(self):
        # Codex round 5, finding 2a: `-c "PROGRAM"` glues PROGRAM's first
        # statement to the `-c "` before it, so `e=A(R,'EXPECTED')` never
        # matched at a true statement start. Unwrapped before splitting.
        gate = RUNNER + "python3 -c \"e=A(R,'EXPECTED'); assert e.value==14\""
        self.assertEqual("14", pins_a_count(gate))

    def test_an_assignment_whose_own_rhs_is_the_comparison_is_refused(self):
        # Codex round 5, finding 2b: `_ASSIGN_STMT` recognised this as an
        # assignment and moved on without ever reading its own right side.
        self.assertEqual("15", pins_a_count(RUNNER + "pinned = EXPECTED == 15"))

    def test_a_reversed_nested_len_call_is_refused(self):
        # Codex round 5, finding 3: `[^)]*` stopped at tuple(...)'s own
        # close-paren, one short of len(...)'s -- missing the "==" that
        # followed. One level of nested parens is now balanced.
        gate = RUNNER + "assert len(tuple(MODULES)) == EXPECTED"
        self.assertEqual("len(tuple(MODULES))", pins_a_count(gate))

    def test_an_unrelated_expected_with_no_runner_reference_is_accepted(self):
        # Codex round 6, finding 1: the rule is about the runner's
        # EXPECTED, not any variable that happens to share the name --
        # scoped to gates that mention a run_all module.
        self.assertIsNone(pins_a_count("assert EXPECTED == 3"))

    def test_a_parenthesised_literal_operand_is_still_refused(self):
        # Codex round 6, finding 2
        self.assertEqual("(15)", pins_a_count(RUNNER + "assert EXPECTED == (15)"))

    def test_a_parenthesised_operand_is_refused_in_either_order(self):
        self.assertEqual("(15)", pins_a_count(RUNNER + "assert (15) == EXPECTED"))

    def test_a_grep_source_pin_with_anchors_is_refused(self):
        # Codex round 6, finding 3: a grep on run_all.py's own source line
        # pins the count just as hard as a Python-level comparison.
        gate = "grep -q '^EXPECTED = 15$' run_all.py"
        self.assertEqual("15", pins_a_count(gate))

    def test_a_fixed_string_grep_source_pin_is_also_refused(self):
        gate = "grep -qF 'EXPECTED = 15' run_all.py"
        self.assertEqual("15", pins_a_count(gate))

    def test_a_grep_for_the_assignment_prefix_with_no_number_is_accepted(self):
        gate = "grep -q '^EXPECTED = ' run_all.py"
        self.assertIsNone(pins_a_count(gate))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
