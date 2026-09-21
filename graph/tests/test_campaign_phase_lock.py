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

EXPECTED_TESTS = 2


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

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
