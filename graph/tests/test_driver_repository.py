"""Driver, planner and doctor follow the campaign from another repository."""

import contextlib
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import graph_commands
import tmp_root  # noqa: F401
from campaign_repo import git
from test_driver import graph_goal
from test_keep import repo
from test_loop import Fakes, repo_with, task
from test_turn_slice import tree_with
from workspace import Workspace
from worktree import Worktree


class DriverRepositoryTest(unittest.TestCase):
    def setUp(self):
        root, self.book, _ = repo_with(task())
        self.repo = pathlib.Path(root)
        self.other = pathlib.Path(repo())
        self.space = Workspace(tempfile.mkdtemp())
        (self.space.root / "contact").write_text("person@example.test\n")
        self.argv = ["--workspace", str(self.space.root)]
        self.env = mock.patch.dict(os.environ, GRAPH_REPO="", GRAPH_BRANCH="campaign/test")
        self.env.start()
        self.addCleanup(self.env.stop)

    def init(self):
        for args in (["init", "--backlog", str(self.book.path), "--source", "a.py"], ["approve"]):
            done = subprocess.run([sys.executable, "-B", graph_goal.__file__, *self.argv, *args],
                                  cwd=self.repo, capture_output=True, text=True, check=False)
            self.assertEqual(0, done.returncode, done.stdout + done.stderr)

    def test_init_records_the_checkout_root_and_an_absolute_backlog(self):
        child = self.repo / "child"
        child.mkdir()
        with contextlib.chdir(child), contextlib.redirect_stdout(io.StringIO()):
            graph_goal.main(self.argv + ["init", "--backlog", "../backlog.yaml"])
        first = self.space.events()[0]
        self.assertEqual(str(self.repo), first["repo"])
        self.assertEqual(str(self.book.path), first["backlog"])

    def test_foreign_cwd_driver_builds_and_keeps_in_the_recorded_repository(self):
        self.init()
        retained = Worktree(str(self.repo), "T1", git(self.repo, "rev-parse", "HEAD"))
        retained.create()
        self.book.note("T1", rebuild_from=retained.path)
        git(self.repo, "commit", "--allow-empty", "-qm", "fixture: advance the campaign")
        git(self.repo, "update-ref", "refs/heads/campaign/test", "HEAD")
        fakes = Fakes()
        other_head = git(self.other, "rev-parse", "HEAD")
        with contextlib.chdir(self.other), contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(graph_goal, "_real_build", fakes.builder), \
                mock.patch.object(graph_goal, "_real_review", fakes.reviewer):
            self.assertEqual(0, graph_goal.main(self.argv + ["run", "--lanes", "1", "--max-tasks", "1"]))
        self.assertEqual("done", self.book.task("T1")["status"],
                         [row.get("why") for row in self.space.events() if row["kind"] == "failed"])
        # Whichever account survives this machine's sign-in check builds it:
        # this card's subject is the repository, not the account it was routed to.
        self.assertTrue([call for call in fakes.calls if call.startswith("build:")],
                        fakes.calls)
        self.assertEqual("two", git(self.repo, "show", "campaign/test:a.py"))
        self.assertEqual(other_head, git(self.other, "rev-parse", "HEAD"))
        alerts = [row for row in self.space.events()
                  if row["kind"] == "alert" and row.get("task") == "workspace repository"]
        self.assertEqual(1, len(alerts))
        self.assertFalse(any(row["kind"] == "quarantined" for row in self.space.events()))

    def test_plan_cuts_and_removes_its_checkout_in_the_recorded_repository(self):
        book = tree_with(dict(task(), status="needs_slice", triage="work"))
        self.space.init(goal="g", backlog=str(book.path), branch="campaign/test", repo=str(self.repo))
        self.space.event("sources_declared", sources=["a.py"])
        (self.space.root / "approved").touch()
        git(self.repo, "branch", "campaign/test")
        seen = []

        def slicer(argv, **kwargs):
            clean = pathlib.Path(argv[argv.index("--repo") + 1])
            seen.append(clean)
            self.assertEqual(git(self.repo, "rev-parse", "HEAD"), git(clean, "rev-parse", "HEAD"))
            self.assertEqual("one\n", (clean / "a.py").read_text())
            return subprocess.CompletedProcess(argv, 0, "covered: unchanged", "")

        with contextlib.chdir(self.other), mock.patch("runner.run", side_effect=slicer), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, graph_goal.main(self.argv + ["plan", "--rounds", "1"]))
        self.assertEqual(1, len(seen))
        self.assertFalse(seen[0].exists())
        self.assertNotIn(str(seen[0]), git(self.repo, "worktree", "list"))

    def test_restarting_the_driver_does_not_repeat_the_repository_alert(self):
        self.book.path.write_text(yaml.safe_dump({"tasks": []}))
        self.init()
        for _ in range(2):
            done = subprocess.run([sys.executable, "-B", graph_goal.__file__, *self.argv, "run"],
                                  cwd=self.other, capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(1, done.returncode, done.stdout + done.stderr)  # sources unplanned
        alerts = [row for row in self.space.events()
                  if row["kind"] == "alert" and row.get("task") == "workspace repository"]
        self.assertEqual(1, len(alerts))

    def test_doctor_reads_a_relative_backlog_against_the_recorded_root(self):
        self.space.init(goal="g", backlog="backlog.yaml", repo=str(self.repo))
        (self.other / "backlog.yaml").write_text(yaml.safe_dump({"tasks": []}))
        output = io.StringIO()
        with contextlib.chdir(self.other), contextlib.redirect_stdout(output), \
                mock.patch.object(graph_commands, "diagnose", side_effect=lambda book, space: (
                    self.assertEqual(["T1"], [row["id"] for row in book.tasks()]) or [])):
            self.assertEqual(0, graph_goal.main(self.argv + ["doctor"]))


if __name__ == "__main__":
    unittest.main()
