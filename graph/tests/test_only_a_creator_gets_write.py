"""Every code builder gets both writing tools; file scope bounds the edits.

Split from `test_loop_live` at the 200-line cap; it was never about live
tasks. Tool choice does not grant extra files.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import where
from test_loop import task
from tools import builder_tools

EXPECTED_TESTS = 1


class MayAddToolsTest(unittest.TestCase):
    def test_every_code_builder_gets_edit_and_write(self):
        self.assertIn(",Edit,Write,", builder_tools(task(files=["README.md"]), str(where.loop())))
        self.assertIn(",Edit,Write,", builder_tools(task(may_add_files=True)))
        self.assertNotIn("Write", builder_tools(task(gate_has_side_effects=True, may_add_files=True,
                                                     files=["state/x.txt"], helper_verbs=["journal"])))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
