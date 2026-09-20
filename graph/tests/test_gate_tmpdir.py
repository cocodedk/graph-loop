"""A gate's temp files land in its own home, which run_gate removes: the test
suites leave ~190 worktrees per run, and in the host's /tmp they stayed."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import gate_sandbox

EXPECTED_TESTS = 2


class GateTmpdirTest(unittest.TestCase):
    def test_a_gate_scratch_dir_is_its_home(self):
        env = gate_sandbox.environment("/tmp/gate-home-x")
        self.assertEqual("/tmp/gate-home-x", env["TMPDIR"])
        self.assertEqual("/tmp/gate-home-x", env["HOME"])


class CountTest(unittest.TestCase):
    def test_count(self):
        names = unittest.defaultTestLoader.getTestCaseNames
        total = sum(len(names(case)) for case in (GateTmpdirTest, CountTest))
        self.assertEqual(EXPECTED_TESTS, total)


if __name__ == "__main__":
    unittest.main()
