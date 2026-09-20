"""Which builder gets the tool that creates a file.

Split from `test_loop_live` at the 200-line cap; it was never about live
tasks. Edit changes what exists; only Write makes a file.
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
    def test_only_a_creator_gets_the_tool_that_creates(self):
        # Edit changes what exists; a split needs Write (T26.v3 could not split),
        # and so does a card whose listed file is not made yet (T26.observed).
        # A card whose files all exist gets no Write.
        self.assertNotIn("Write", builder_tools(task(files=["README.md"]), str(where.loop())))
        self.assertIn(",Write,", builder_tools(task(may_add_files=True)))
        self.assertNotIn("Write", builder_tools(task(gate_has_side_effects=True, may_add_files=True,
                                                     files=["state/x.txt"], helper_verbs=["journal"])))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
