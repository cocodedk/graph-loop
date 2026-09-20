"""An HTTP route quoted in a grep pattern is not a checkout path.

`/health/ready` and `/findings/fnd-beacon-0006/triage` have the same shape as
`/srv/other-checkout` — a leading slash, two or more segments — but they sit
inside a grep pattern's quotes, which are blanked out before the path search
ever runs. (`/source-state` has only one segment and was already exempt; it
rides along below because it sits in the same real gate as `/health/ready`,
the token that actually tripped the false positive.) The three real cards
below were flagged as reaching into some other checkout when their gates
never left this one.

Whether a path's first segment happens to exist at this host's root proves
nothing either way: `/workspace/other-checkout` names a checkout even where
`/workspace` does not exist, and `grep -q '/opt/ready'` names none even
though `/home` exists on every host that runs this suite.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from doctor import check_backlog
from test_doctor import book

EXPECTED_TESTS = 16


class ARouteQuotedInAGrepPatternIsNotAPath(unittest.TestCase):
    def test_the_triage_health_pair_gate_is_not_named(self):
        out = check_backlog(book(
            gate="(cd simulation/tests/triage && grep -q '/health/live' "
                 "test_health_doors.py) && (cd simulation/tests/triage && "
                 "grep -q '/health/ready' test_health_doors.py) && (cd "
                 "simulation/tests/triage && grep -q "
                 "'/findings/fnd-beacon-0006/triage' test_health_doors.py)"))
        self.assertEqual([], [c for c in out if "absolute path" in c.what])

    def test_the_network_sensor_source_state_gate_is_not_named(self):
        out = check_backlog(book(
            gate="(cd simulation/tests/network-sensor && grep -q "
                 "'/source-state' test_source_state.py) && (cd "
                 "simulation/tests/network-sensor && grep -q '/health/ready' "
                 "test_source_state.py)"))
        self.assertEqual([], [c for c in out if "absolute path" in c.what])

    def test_a_real_root_is_still_named(self):
        # the fix must not swallow the fault it exists to catch
        out = check_backlog(book(
            gate="cd /srv/projects/other-checkout && python3 -m unittest a"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_checkout_path_is_named_even_off_a_root_that_does_not_exist(self):
        # root existence is not the test: this checkout path is real even
        # though nothing called /workspace exists on this host
        out = check_backlog(book(
            gate="cd /workspace/other-checkout && make"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_grep_pattern_is_exempt_even_under_a_root_that_exists(self):
        # /home exists on this host, but the quotes still belong to grep
        out = check_backlog(book(gate="grep -q '/opt/ready' file.py"))
        self.assertEqual([], [c for c in out if "absolute path" in c.what])

    def test_a_grep_file_argument_is_still_named(self):
        # -f/--file take a FILE to read patterns FROM, not a pattern — that
        # argument names a real checkout and must not be blanked away
        out = check_backlog(book(
            gate="grep -f '/srv/other-checkout/patterns' input"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_double_dash_before_the_pattern_still_exempts_it(self):
        # `--` ends option parsing; the old scrubber only recognised
        # `-[A-Za-z]+`-shaped flags glued straight to the pattern and missed
        # this valid form entirely
        out = check_backlog(book(gate="grep -- '/health/ready' file"))
        self.assertEqual([], [c for c in out if "absolute path" in c.what])

    def test_a_short_option_with_a_separate_argument_still_exempts_the_pattern(self):
        # `-m 1` is `-m` and its count as two words, not one flag glued to
        # the pattern — the old scrubber expected the pattern right after
        # the flags and missed this valid form too
        out = check_backlog(book(gate="grep -m 1 '/health/ready' file"))
        self.assertEqual([], [c for c in out if "absolute path" in c.what])

    def test_a_file_argument_is_still_named_alongside_an_explicit_pattern(self):
        # -e already supplies the pattern; -f's own argument is still a
        # real file and must still be judged — this already passed before
        # the fix too, and must keep passing
        out = check_backlog(book(
            gate="grep -e '/health/ready' -f '/srv/other/patterns' input"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_an_awk_program_spanning_lines_is_not_named(self):
        # the real run stage of a card of the first campaign's
        # triage-decision-binds-its-inputs card: awk's whole quoted PROGRAM
        # is one operand, blanked as a unit even though it holds several
        # /regex/{action} clauses spread across lines
        out = check_backlog(book(gate=(
            "(cd simulation/tests/triage &&\n"
            "  timeout 600 python3 -m unittest -v test_input_binding 2>&1 |\n"
            "  awk '/test_the_decision_names_the_bytes_it_read/{n=1}\n"
            "       /^Ran 1 test /{r=1}\n"
            "       /skipped/{s=1}\n"
            "       /^OK$/{o=1}\n"
            "       END{exit !(n && r && o && !s)}')"
        )))
        self.assertEqual([], [c for c in out if "absolute path" in c.what])

    def test_a_sed_script_is_not_named(self):
        # sed reads its own program the way grep reads its pattern; -n is a
        # bare flag, so the quoted script is the first word left over
        out = check_backlog(book(gate="sed -n '/health/ready/p' file"))
        self.assertEqual([], [c for c in out if "absolute path" in c.what])

    def test_a_tool_name_used_as_an_operand_is_not_reparsed_as_a_command(self):
        # "sed" here is grep's own pattern, not a command — matching a tool
        # name anywhere let a bogus second parse start there and consume
        # the real file operand, blanking away the path it should name
        out = check_backlog(book(gate="grep -q sed /srv/other/file"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_newline_inside_a_quoted_pattern_is_not_a_command_boundary(self):
        # the quote never closes before "sed" — a real command boundary is
        # one of ; & | ( { or a newline OUTSIDE any quotes, and this
        # newline sits inside grep's own still-open pattern
        out = check_backlog(book(
            gate="grep -q 'foo\nsed' /srv/other/file"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_sed_long_file_option_is_still_named(self):
        # --file is the long form of -f: a real script to read FROM, not
        # sed's own pattern — unrecognised before, it fell through to the
        # bare-operand fallback and got blanked by mistake
        out = check_backlog(book(gate="sed --file /srv/other/script input"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_backslash_newline_continuation_does_not_end_the_command(self):
        # a real shell joins a trailing backslash-newline into the next
        # line; treating it as a boundary ended the scan early and left
        # the quoted pattern's route unblanked
        out = check_backlog(book(gate="grep -q \\\n'/health/ready' file"))
        self.assertEqual([], [c for c in out if "absolute path" in c.what])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
