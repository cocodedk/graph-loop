"""A run whose provisioning git would carry into every diff never starts.

One campaign linked node_modules into every checkout while its .gitignore said
`node_modules/`, a pattern for folders that a link does not match. The link
entered every build's diff, and 352 attempts kept nothing. One probe checkout of
the campaign's tip, made before any card is started, finds it for free.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))
import provision_check
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_supervisor_stand_down import run_supervisor
from workspace import Workspace

_spec = importlib.util.spec_from_file_location("graph_goal", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 9


def repo(ignore: str) -> str:
    """A repository whose committed .gitignore is `ignore`, with node_modules installed."""
    root = tempfile.mkdtemp()
    for args in (("git", "init", "-q", "-b", "main"),
                 ("git", "config", "user.email", "t@example.test"),
                 ("git", "config", "user.name", "test")):
        subprocess.run(args, cwd=root, capture_output=True, check=True)
    pathlib.Path(root, ".gitignore").write_text(ignore, "utf-8")
    subprocess.run(("git", "add", "-A"), cwd=root, capture_output=True, check=True)
    subprocess.run(("git", "commit", "-qm", "first"), cwd=root, capture_output=True, check=True)
    pathlib.Path(root, "node_modules", "acorn").mkdir(parents=True)
    return root


def probes() -> list[pathlib.Path]:
    return list(pathlib.Path(tempfile.gettempdir()).glob("graph-provision-check-*"))


class RefusalTest(unittest.TestCase):
    def test_a_link_git_would_carry_refuses_the_run(self):
        root = repo("node_modules/\n")
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": "node_modules"}):
            why = provision_check.refusal(root, "campaign/test")
        self.assertIn("?? node_modules", why)
        self.assertIn("without the '/'", why)
        self.assertEqual([], probes(), "the probe checkout is removed")

    def test_an_ignored_link_lets_the_run_start(self):
        root = repo("node_modules\n")
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": "node_modules"}):
            self.assertEqual("", provision_check.refusal(root, "campaign/test"))

    def test_the_probe_reads_the_branch_as_the_keeper_does(self):
        # a tag with the branch's name never answers for it
        root = repo("node_modules/\n")
        git = lambda *args: subprocess.run(("git", *args), cwd=root, capture_output=True, check=True)
        git("tag", "campaign/x")
        git("switch", "-q", "-c", "campaign/x")
        pathlib.Path(root, ".gitignore").write_text("node_modules\n", "utf-8")
        git("commit", "-qam", "ignore the link")
        git("switch", "-q", "main")        # a campaign branch is never the checked-out one
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": "node_modules"}):
            self.assertEqual("", provision_check.refusal(root, "campaign/x"))

    def test_a_branch_not_made_yet_is_probed_at_head(self):
        root = repo("node_modules/\n")
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": "node_modules"}):
            self.assertIn("?? node_modules", provision_check.refusal(root, "campaign/later"))

    def test_a_read_only_copied_folder_leaves_no_probe_behind(self):
        root = repo("runtime\n")
        runtime = pathlib.Path(root, "runtime")
        runtime.mkdir()
        (runtime / "key.txt").write_text("minted", "utf-8")
        runtime.chmod(0o555)
        self.addCleanup(runtime.chmod, 0o755)
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_COPY": "runtime"}):
            self.assertEqual("", provision_check.refusal(root, "campaign/test"))
        self.assertEqual([], probes())

    def test_the_supervisor_stands_down_before_it_plans(self):
        # a refusal and a probe that failed are the same stand-down: only a safe
        # answer lets a plan phase be paid for
        for said in ("the run did not start: git would carry  ?? node_modules",
                     "Traceback: OSError: the probe checkout could not be made"):
            with self.subTest(said=said):
                log, code, camp = run_supervisor(self, run_exit=0, provision_refused=said)
                self.assertEqual(1, code)                        # a loop that gave up
                self.assertNotIn("planning", log)                # no slicer paid on it
                self.assertNotIn("starting the driver", log)
                self.assertIn(said.split(": ")[-1], (camp / "prompt.txt").read_text("utf-8"))

    def test_the_probe_exits_0_only_when_provisioning_is_safe(self):
        lib = HERE / "lib" / "provision_check.py"
        for ignore, link, ok in (("node_modules\n", "node_modules", True),
                                 ("node_modules/\n", "node_modules", False),
                                 (None, "node_modules", False)):        # no repository: it fails
            with self.subTest(ignore=ignore):
                root = repo(ignore) if ignore else tempfile.mkdtemp()
                space = Workspace(pathlib.Path(tempfile.mkdtemp()) / "campaign").init(
                    goal="the backlog", backlog=str(pathlib.Path(root) / "b.yaml"),
                    branch="campaign/test", repo=root)
                env = dict(os.environ, GRAPH_PROVISION_LINK=link)
                done = subprocess.run((sys.executable, str(lib), str(space.root)), env=env,
                                      capture_output=True, text=True, check=False)
                self.assertEqual(ok, done.returncode == 0, done.stdout + done.stderr)

    def test_nothing_provisioned_makes_no_checkout(self):
        with (mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": "",
                                           "GRAPH_PROVISION_COPY": ""}),
              mock.patch.object(provision_check, "Worktree") as made):
            self.assertEqual("", provision_check.refusal("/nowhere", "main"))
        made.assert_not_called()

    def test_a_refused_run_stops_before_the_driver_claims_the_campaign(self):
        root = pathlib.Path(tempfile.mkdtemp())
        backlog = root / "b.yaml"
        backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": []}))
        space = Workspace(root / "campaign").init(goal="the backlog", backlog=str(backlog))
        (space.root / "approved").write_text("approved\n", "utf-8")
        args = types.SimpleNamespace(workspace=str(space.root), dry_run=False, lanes=3,
                                     max_tasks=0, idle_seconds=300, attempt_ceiling=12,
                                     hours_ceiling=2.0)
        with (mock.patch.object(graph_goal.provision_check, "refusal",
                                return_value="git would carry it"),
              self.assertRaises(SystemExit) as stopped):
            graph_goal.command_run(args)
        self.assertEqual("git would carry it", str(stopped.exception))
        self.assertEqual([], [row for row in space.events()
                              if row.get("kind") == "driver_started"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
