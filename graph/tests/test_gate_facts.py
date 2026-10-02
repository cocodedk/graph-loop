"""Two gate facts: a card's gate script belongs to one loop process, so two projects building the same
feature name never share it; and a sandbox probe that hangs is a box that does not work, never a raise."""

import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import gate_sandbox
import tmp_root  # noqa: F401
from gate_script import gate_script_path

EXPECTED_TESTS = 2


class Facts(unittest.TestCase):
    def test_the_gate_script_is_this_processs_own(self):
        self.assertTrue(pathlib.Path(gate_script_path({"id": "01-first"})).name.startswith(f"{os.getpid()}-"))

    def test_a_hanging_probe_means_no_box(self):
        with mock.patch.object(gate_sandbox, "_WORKS", None), mock.patch.object(gate_sandbox, "BWRAP", "bwrap"), \
                mock.patch.object(gate_sandbox.subprocess, "run", side_effect=subprocess.TimeoutExpired("bwrap", 30)):
            self.assertFalse(gate_sandbox.works())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
