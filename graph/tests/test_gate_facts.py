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

EXPECTED_TESTS = 4


class Facts(unittest.TestCase):
    def test_the_gate_script_is_this_processs_own(self):
        self.assertTrue(pathlib.Path(gate_script_path({"id": "01-first"})).name.startswith(f"{os.getpid()}-"))

    def test_a_hanging_probe_means_no_box(self):
        with mock.patch.object(gate_sandbox, "_WORKS", None), mock.patch.object(gate_sandbox, "BWRAP", "bwrap"), \
                mock.patch.object(gate_sandbox.subprocess, "run", side_effect=subprocess.TimeoutExpired("bwrap", 30)):
            self.assertFalse(gate_sandbox.works())


class Masks(unittest.TestCase):
    def test_a_path_reached_through_a_link_is_masked_once(self):
        # /var/run -> /run made bubblewrap mount the docker socket twice and refuse to start: no box at all
        import tempfile
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "run").mkdir()
        (root / "var-run").symlink_to(root / "run")
        with mock.patch.object(gate_sandbox, "MASKED", (str(root / "run"), str(root / "var-run"))), \
                mock.patch.object(gate_sandbox, "BWRAP", "bwrap"):
            line = gate_sandbox.argv("true", str(root), str(root))
        self.assertEqual(1, sum(1 for i, word in enumerate(line) if word == "--tmpfs" and line[i + 1] == str(root / "run")))
        self.assertNotIn(str(root / "var-run"), line)

    def test_the_probe_asks_that_the_real_home_shows_nothing(self):
        self.assertIn(os.path.expanduser("~"), gate_sandbox.PROBE)
        self.assertIn("test -w / && exit 1", gate_sandbox.PROBE)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
