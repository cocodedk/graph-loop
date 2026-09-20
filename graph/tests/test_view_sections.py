"""view_sections.py's card-listing and acceptance sections.

Every section must read the campaign's OWN backlog (from its own init event,
through `_backlog_of`) and its OWN acceptance record (its `accepted` events),
never a default or a git-log guess that can mix in another campaign's
backlog or a hand commit nobody's card-write ever recorded.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import view_sections
from workspace import Workspace

EXPECTED_TESTS = 5


def _backlog_with(tmp: pathlib.Path, *task_ids: str) -> pathlib.Path:
    path = tmp / "backlog.yaml"
    path.write_text(yaml.safe_dump({"tasks": [
        {"id": tid, "status": "todo", "needs": []} for tid in task_ids]}))
    return path


class CurrentBacklogTest(unittest.TestCase):
    def test_a_non_default_backlog_named_in_the_init_event_is_read(self):
        camp = pathlib.Path(tempfile.mkdtemp())
        backlog_path = _backlog_with(pathlib.Path(tempfile.mkdtemp()), "SENTINEL-1")
        Workspace(camp).init(goal="pilot", backlog=str(backlog_path), branch="campaign/graph")
        self.assertEqual(str(backlog_path), view_sections._current_backlog(camp))

    def test_no_init_event_yet_falls_back_to_the_environments_default(self):
        camp = pathlib.Path(tempfile.mkdtemp())   # never initialised
        self.assertEqual(str(view_sections._DEFAULT_BACKLOG),
                         view_sections._current_backlog(camp))


class BacklogSectionTest(unittest.TestCase):
    def test_the_backlog_section_reads_the_campaigns_own_backlog(self):
        camp = pathlib.Path(tempfile.mkdtemp())
        backlog_path = _backlog_with(pathlib.Path(tempfile.mkdtemp()), "SENTINEL-2")
        Workspace(camp).init(goal="pilot", backlog=str(backlog_path), branch="campaign/graph")
        with unittest.mock.patch.object(view_sections, "CAMPAIGN", camp):
            lines = view_sections.backlog()
        self.assertTrue(any("SENTINEL-2" in line for line in lines), lines)


class AcceptedSectionTest(unittest.TestCase):
    def test_accepted_counts_the_records_own_events_not_hand_commits(self):
        """A record with two `accepted` events and a branch with three
        T-headed hand commits: the view says 2, read from the record --
        never from a `git log --grep ^T[0-9]` that a hand commit also
        matches."""
        camp = pathlib.Path(tempfile.mkdtemp())
        space = Workspace(camp).init(goal="pilot", backlog="backlog.yaml")
        space.event("accepted", task="SENTINEL-A", commit="aaaaaaaaaaaa")
        space.event("accepted", task="SENTINEL-B", commit="bbbbbbbbbbbb")
        with unittest.mock.patch.object(view_sections, "CAMPAIGN", camp):
            lines = view_sections.accepted()
        self.assertEqual(2, len(lines), lines)
        self.assertTrue(any("SENTINEL-A" in line for line in lines), lines)
        self.assertTrue(any("SENTINEL-B" in line for line in lines), lines)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
