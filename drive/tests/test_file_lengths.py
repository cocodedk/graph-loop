"""No code or test file of the loop passes 200 lines.

The rule is in CLAUDE.md and nothing enforced it, so `lib/workspace.py` grew to
215 and an independent reviewer had to say so. An oversized file splits at the
next fixpoint; this says the moment one goes over, and names it.
"""

from __future__ import annotations

import pathlib
import unittest

LOOPS = pathlib.Path(__file__).resolve().parents[2]   # the repository root
CAP = 200

EXPECTED_TESTS = 1


class LengthTest(unittest.TestCase):
    def test_no_python_file_of_the_drive_loop_or_the_slicer_passes_the_cap(self):
        over = {}
        for folder in ("drive", "slicer"):
            for path in sorted((LOOPS / folder).rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                lines = len(path.read_text("utf-8").splitlines())
                if lines > CAP:
                    over[str(path.relative_to(LOOPS))] = lines
        self.assertEqual({}, over, "these split at this fixpoint")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
