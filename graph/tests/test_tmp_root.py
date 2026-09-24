"""A focused run of any one test module leaves nothing in /tmp: the guard is
imported by every module that makes temp files, not only by the shared helpers
a full run happens to import first (Codex, bit-astra-tmp-root)."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parent
EXPECTED_TESTS = 2


class FocusedRunTest(unittest.TestCase):
    def test_a_focused_run_of_one_module_leaves_its_tmp_empty(self):
        with tempfile.TemporaryDirectory() as scratch:
            done = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(HERE),
                                   "-p", "test_backlog.py"], cwd=str(HERE.parent),
                                  env={"PATH": "/usr/bin:/bin", "TMPDIR": scratch, "HOME": scratch},
                                  capture_output=True, text=True, check=False)
            self.assertEqual(0, done.returncode, done.stderr[-800:])
            self.assertIn("OK", done.stderr)
            self.assertEqual([], sorted(pathlib.Path(scratch).iterdir()), "the focused run left files behind")

    def test_every_module_that_makes_temp_files_imports_the_guard(self):
        unguarded = [p.name for p in HERE.glob("test_*.py")
                     if "tempfile" in p.read_text() and "import tmp_root" not in p.read_text()]
        self.assertEqual([], unguarded)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(str(HERE), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
