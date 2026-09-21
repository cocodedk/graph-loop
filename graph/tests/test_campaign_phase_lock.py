"""Planning and building are mutually exclusive across command processes."""

import fcntl
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import yaml

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
from workspace import Workspace

EXPECTED_TESTS = 4


class PhaseLockTest(unittest.TestCase):
    def test_planning_cannot_write_while_the_driver_owns_the_campaign(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            backlog = root / "backlog.yaml"
            backlog.write_text(yaml.safe_dump({"tasks": [{"id": "retry", "status": "lane_failed",
                "goal": "retry", "files": ["a.py"], "gate": "false", "triage": "harness"}]}))
            space = Workspace(root / "campaign").init(goal="test", backlog=str(backlog))
            (space.root / "approved").write_text("approved\n")
            before = backlog.read_bytes()
            with (space.root / "driver.lock").open("w") as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                done = subprocess.run([sys.executable, str(HERE / "graph-goal.py"),
                    "--workspace", str(space.root), "plan", "--rounds", "1"],
                    capture_output=True, text=True, timeout=10, check=False,
                    env={**os.environ, "GRAPH_REPO": str(root)})
            self.assertNotEqual(0, done.returncode, "planning must refuse the held driver lock")
            self.assertEqual(before, backlog.read_bytes())
            self.assertFalse(any(row["kind"] == "plan_started" for row in space.events()))

    def test_uncontended_planning_completes(self):
        self._run_planner(False)

    def test_planning_lock_refuses_driver(self):
        self._run_planner(True)

    def _run_planner(self, probe_driver):
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            backlog = root / "backlog.yaml"
            backlog.write_text(yaml.safe_dump({"tasks": []}))
            space = Workspace(root / "campaign").init(goal="test", backlog=str(backlog))
            (space.root / "approved").write_text("approved\n")
            # A real planning process, with only paid slicing replaced; its
            # callback starts the real build CLI while planning is in progress.
            script = """
import subprocess, sys, types
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from plan_phase import command_plan

def slice_pending(book, space):
    if sys.argv[4] == "probe":
        child = subprocess.run([sys.executable, sys.argv[2], "--workspace",
            str(space.root), "run", "--max-tasks", "1"],
            capture_output=True, text=True, timeout=10, check=False)
        assert child.returncode != 0, "builder entered while planning"
        assert "another driver already holds" in child.stderr, child.stderr
    print("planner reached slicing")

with patch("plan_phase.slice_pending", side_effect=slice_pending):
    result = command_plan(types.SimpleNamespace(workspace=sys.argv[3], rounds=1))
assert result == 0, result
"""
            done = subprocess.run([sys.executable, "-c", script, str(HERE / "lib"),
                str(HERE / "graph-goal.py"), str(space.root),
                "probe" if probe_driver else "plain"],
                capture_output=True, text=True, timeout=20, check=False,
                env={**os.environ, "GRAPH_REPO": str(root)})
            self.assertEqual(0, done.returncode, done.stdout + done.stderr)
            self.assertIn("planner reached slicing", done.stdout)
            self.assertTrue(any(row["kind"] == "plan_started" for row in space.events()))

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
