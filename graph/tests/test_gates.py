"""A gate decides, and it decides on its exit code.

Written before `gates.py`. The rules under test are ones that cost real money:
a gate is proved red before a builder starts; its verdict is the process's exit
code, never text a grep happened to match; and it prints every failure it counts.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from gates import prove_red, run_gate

EXPECTED_TESTS = 9


def workdir() -> str:
    return tempfile.mkdtemp()


class RunTest(unittest.TestCase):
    def test_a_zero_exit_passes_whatever_it_printed(self):
        out = run_gate("echo 'GATE: something failed'; exit 0", workdir())
        self.assertTrue(out.passed)
        self.assertIn("GATE: something failed", out.output)

    def test_a_non_zero_exit_fails_whatever_it_printed(self):
        out = run_gate("echo 'GATE: package 99 passes'; exit 1", workdir())
        self.assertFalse(out.passed)

    def test_a_pipeline_is_judged_by_its_own_status(self):
        # `gate | grep` used to commit red work because grep found its lines.
        out = run_gate("set -o pipefail; (echo GATE; exit 1) | grep GATE", workdir())
        self.assertFalse(out.passed)

    def test_a_gate_that_never_returns_fails_instead_of_hanging(self):
        out = run_gate("sleep 30", workdir(), timeout=1)
        self.assertFalse(out.passed)
        self.assertEqual("timeout", out.kind)

    def test_the_whole_output_is_kept_for_the_record(self):
        out = run_gate("echo one; echo two >&2; exit 3", workdir())
        self.assertIn("one", out.output)
        self.assertIn("two", out.output)
        self.assertEqual(3, out.code)


class RedFirstTest(unittest.TestCase):
    def test_a_gate_that_is_already_green_refuses_the_task(self):
        ok, why = prove_red("exit 0", workdir())
        self.assertFalse(ok)
        self.assertIn("already passes", why)

    def test_a_gate_that_fails_for_the_expected_reason_is_proved(self):
        ok, why = prove_red("echo 'GATE: the loader still ignores the document'; exit 1",
                            workdir(), expect="still ignores the document")
        self.assertTrue(ok, why)

    def test_a_gate_that_fails_for_another_reason_is_not_proved(self):
        ok, why = prove_red("echo 'GATE: suite red'; exit 1", workdir(),
                            expect="still ignores the document")
        self.assertFalse(ok)
        self.assertIn("suite red", why)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
