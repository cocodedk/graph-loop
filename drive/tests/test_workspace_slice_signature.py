"""needs_slice groups gate failures by their normalised reason: a flaky
failure and a real one are two different problems, not one stuck task."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from workspace import Workspace

EXPECTED_TESTS = 3


def fresh() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="backlog.yaml")


class SliceSignatureTest(unittest.TestCase):
    def test_two_gate_failures_with_different_reasons_do_not_ask_for_a_slice(self):
        space = fresh()
        space.attempt("T1", account="work", kind="ok", failed_gate=True)
        space.event("failed", task="T1", step="gate", why="flaky: connection refused")
        space.attempt("T1", account="personal", kind="ok", failed_gate=True)
        space.event("failed", task="T1", step="gate", why="AssertionError on line 40")
        self.assertFalse(space.needs_slice("T1"))

    def test_two_gate_failures_with_the_same_reason_ask_for_a_slice(self):
        space = fresh()
        space.attempt("T1", account="work", kind="ok", failed_gate=True)
        space.event("failed", task="T1", step="gate", why="AssertionError on line 40")
        space.attempt("T1", account="personal", kind="ok", failed_gate=True)
        space.event("failed", task="T1", step="gate", why="AssertionError on line 40")
        self.assertTrue(space.needs_slice("T1"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
