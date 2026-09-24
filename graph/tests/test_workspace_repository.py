"""An existing workspace selects its repository without consulting the cwd."""

import contextlib
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401
import where
from campaign_of import backlog_of
from test_keep import repo
from workspace import Workspace
from workspace_repo import alert_cwd


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(repo())
        self.other = pathlib.Path(repo())
        self.space = Workspace(tempfile.mkdtemp())
        self.space.event("init", goal="g", backlog=str(self.repo / "backlog.yaml"))

    def test_absolute_approved_sources_migrate_once_and_preserve_history(self):
        self.space.event("sources_declared", sources=[str(self.repo / "a.py")])
        history = (self.space.root / "events.jsonl").read_bytes()
        with contextlib.chdir(self.other), mock.patch.dict(os.environ, GRAPH_REPO=str(self.other)):
            self.assertEqual(self.repo, where.repo(self.space))
            self.assertEqual(self.repo, where.repo(Workspace(self.space.root)))
        self.assertTrue((self.space.root / "events.jsonl").read_bytes().startswith(history))
        self.assertEqual(1, sum(row["kind"] == "repository_declared"
                                for row in self.space.events()))

    def test_relative_sources_use_the_recorded_backlog_anchor(self):
        self.space.event("sources_declared", sources=["a.py"])
        with contextlib.chdir(self.other), mock.patch.dict(os.environ, GRAPH_REPO=""):
            self.assertEqual(self.repo, where.repo(self.space))

    def test_relative_backlog_uses_the_workspace_anchor_and_stays_absolute(self):
        space = Workspace(self.repo / "campaign")
        space.event("init", goal="g", backlog="missing-vault")
        space.event("sources_declared", sources=["a.py"])
        with contextlib.chdir(self.other):
            self.assertEqual(self.repo, where.repo(space))
            self.assertEqual(str(self.repo / "missing-vault"), backlog_of(space))

    def test_unresolvable_sources_do_not_select_the_launch_repository(self):
        space = Workspace(tempfile.mkdtemp())
        space.event("init", goal="g", backlog="vault")
        space.event("sources_declared", sources=["a.py"])
        with contextlib.chdir(self.other), mock.patch.dict(os.environ, GRAPH_REPO=""), \
                self.assertRaisesRegex(SystemExit, "cannot derive"):
            where.repo(space)

    def test_a_read_only_resolution_does_not_migrate_the_ledger(self):
        self.space.event("sources_declared", sources=["a.py"])
        before = (self.space.root / "events.jsonl").read_bytes()
        with contextlib.chdir(self.other):
            self.assertEqual(self.repo, where.repo(self.space, persist=False))
        self.assertEqual(before, (self.space.root / "events.jsonl").read_bytes())

    def test_different_repository_alert_is_written_once_across_reopens(self):
        with contextlib.chdir(self.other):
            alert_cwd(self.space, self.repo)
            alert_cwd(Workspace(self.space.root), self.repo)
        alerts = [row for row in self.space.events() if row["kind"] == "alert"]
        self.assertEqual(1, len(alerts))
        self.assertIn(str(self.repo), alerts[0]["why"])
        self.assertEqual(1, len(self.space.alerts(unread_only=False)))

    def test_a_subdirectory_of_the_same_repository_needs_no_alert(self):
        child = self.repo / "child"
        child.mkdir()
        with contextlib.chdir(child):
            alert_cwd(self.space, self.repo)
        self.assertEqual([], self.space.alerts(unread_only=False))


if __name__ == "__main__":
    unittest.main()
