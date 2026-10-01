"""A gate's failure must reach the builder (issue #250).

stdout and stderr were joined as one then the other, so teardown noise written to stderr came last,
and the repair prompt kept only the last 2000 characters: the line that named the failing test was
cut off, the builder saw noise and changed nothing. The streams now come out in the order they were
written, and the failing lines the tail would drop are kept ahead of it.
"""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import gate_reports
import gates
import tmp_root  # noqa: F401

EXPECTED_TESTS = 5
FAIL = "FAIL  src/ring.test.ts > renders the overdue ring in amber"


class Order(unittest.TestCase):
    def test_the_streams_come_out_in_the_order_they_were_written(self):
        result = gates.run_gate("echo one; echo two >&2; echo three; exit 1", tempfile.mkdtemp(), confine=False)
        self.assertEqual("one\ntwo\nthree\n", result.output)

    def test_a_compound_command_keeps_the_order_too(self):
        result = gates.run_gate("echo one && echo two >&2 && echo three", tempfile.mkdtemp(), confine=False)
        self.assertEqual("one\ntwo\nthree\n", result.output)


class Excerpt(unittest.TestCase):
    def test_a_failing_line_above_a_noisy_tail_is_kept(self):
        noise = "".join(f"close timed out {n}\n" for n in range(300))
        text = f"{FAIL}\nAssertionError: expected amber\n{noise}"
        kept = gate_reports.excerpt(text)
        self.assertIn(FAIL, kept)
        self.assertIn("AssertionError: expected amber", kept)
        self.assertTrue(kept.endswith("close timed out 299\n"))

    def test_a_short_output_is_returned_whole(self):
        text = f"{FAIL}\nok\n"
        self.assertEqual(text, gate_reports.excerpt(text))

    def test_the_failing_lines_kept_are_the_last_twenty_and_each_is_cut(self):
        text = "".join(f"FAIL case {n} " + "x" * 400 + "\n" for n in range(100)) + "tail\n" * 600
        kept = gate_reports.excerpt(text)
        self.assertNotIn("FAIL case 79 ", kept)
        self.assertIn("FAIL case 80 ", kept)
        self.assertNotIn("x" * 201, kept)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the five above and this one


if __name__ == "__main__":
    unittest.main()
