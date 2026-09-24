"""`campaign_of.backlog_of` — the one home for a campaign's own backlog path,
read from its own init event. `graph_commands._backlog_of` turns an empty
answer into an exit; `view_sections._current_backlog` turns it into the
environment's default. Each caller's own test covers that choice; this file
covers the shared function itself.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from campaign_of import backlog_of
from workspace import Workspace

EXPECTED_TESTS = 3


class BacklogOfTest(unittest.TestCase):
    def test_no_init_event_yet_is_the_empty_string(self):
        space = Workspace(tempfile.mkdtemp())   # never initialised
        self.assertEqual("", backlog_of(space))

    def test_an_init_event_naming_a_backlog_returns_that_path(self):
        path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
        space = Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog=str(path))
        self.assertEqual(str(path), backlog_of(space))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
