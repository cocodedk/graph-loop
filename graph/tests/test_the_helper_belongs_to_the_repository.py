"""A live task's helper command belongs to the repository being worked on.

The loop used to name one helper by a fixed path inside the repository it
lived in, so moving the loop anywhere else granted a builder a command that
was not there. `GRAPH_HELPER` names it now, and a machine that names none
gives a live task no helper grant at all.
"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import tools

EXPECTED_TESTS = 2
TASK = {"id": "T1", "gate_has_side_effects": True,
        "helper_verbs": ["free prd-app-04", "journal"]}


class HelperTest(unittest.TestCase):
    def test_a_named_helper_is_what_the_commands_are_built_from(self):
        with mock.patch.dict(os.environ, {"GRAPH_HELPER": "/srv/tools/sc"}):
            self.assertEqual(["/srv/tools/sc free prd-app-04", "/srv/tools/sc journal *"],
                             tools.helper_commands(TASK))

    def test_no_helper_named_means_no_helper_command(self):
        with mock.patch.dict(os.environ, {"GRAPH_HELPER": ""}):
            self.assertEqual([], tools.helper_commands(TASK))



class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
