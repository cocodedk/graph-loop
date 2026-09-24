"""`resume()` is gone. It used to unlink `stop.flag` unconditionally, called
once at driver start (`command_run`, graph-goal.py) before the turn ever got
a chance to read the flag (`turn.turn_opens` -> `stop_or_restart` ->
`stopping`) -- so a flag placed before the driver started was silently
dropped instead of honoured, and a `stop_cleared` event recorded a clearing
that never should have happened.

`command_run` no longer calls it at all, so there is no method left to test
here -- only the behaviour: a flag placed before the driver starts must
still be there, unread task and all, once the turn ends. Proven through the
real entry point (the `test_driver.py` in-process rig), not a bare mixin.

The flag's other, already-correct between-tasks behaviour -- `stop_or_restart`,
`restarting`, `idle`, `stopping` -- is covered in `test_workspace_stop.py`; not
repeated here.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE / "lib"))

from keep import Keeper
from workspace import Workspace

# Loaded by path, once, so this test can monkeypatch the exact name
# `command_run`'s loop body calls -- own module, same approach as
# `test_driver.py` and `test_driver_quarantine.py`, so the three patch
# each other's copy of nothing.
_spec = importlib.util.spec_from_file_location("graph_goal_flags", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 2


def _campaign(tasks: list[dict]) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp())
    backlog = root / "b.yaml"
    backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": tasks}))
    env = {**os.environ, "GRAPH_REPO": str(HERE.parents[1]), "GRAPH_CAMPAIGN": str(root / "campaign"),
          "GRAPH_BACKLOG": str(backlog)}
    init = subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "init",
                           "--backlog", str(backlog), "--branch", "campaign/test-flags"],
                          capture_output=True, text=True, env=env, check=False)
    assert init.returncode == 0, init.stdout + init.stderr
    (root / "campaign" / "approved").write_text("test")
    return root


def _events(root: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in (root / "campaign" / "events.jsonl").read_text().splitlines()
           if line.strip()]


class StopFlagAtDriverStartTest(unittest.TestCase):
    def test_a_flag_placed_before_the_turn_starts_no_task_and_survives_it(self):
        """Mirrors driver start: a person's `graph-goal.py stop` writes
        stop.flag and logs `stop_requested` before the driver ever runs.
        With no `resume()` left to clear it, `turn_opens` is the first and
        only thing that reads the flag -- it ends the turn before a single
        task is picked, and both the flag and its event survive the turn."""
        root = _campaign([{"id": "T1", "goal": "must not run", "status": "todo",
                           "needs": [], "files": ["a.py"]}])
        Workspace(str(root / "campaign")).stop()   # placed before the driver starts
        args = types.SimpleNamespace(workspace=str(root / "campaign"), dry_run=False,
                                     lanes=3, max_tasks=0,
                                     idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)
        started_lanes: list = []

        def fake_run_lanes(loop, book, space, tasks, turn_id=""):
            # Reached only if the stop flag were missed. A real turn would
            # settle these tasks one way or another; without that, the loop
            # would offer T1 again next turn and spin forever -- so this
            # fake settles it, the same way a real lane eventually would.
            started_lanes.append([row["id"] for row in tasks])
            for row in tasks:
                book.set_status(row["id"], "done")
            return len(tasks), False

        with unittest.mock.patch.object(Keeper, "pending", lambda self: []), \
             unittest.mock.patch("publishing.behind", return_value=False), \
             unittest.mock.patch.object(graph_goal, "run_lanes", fake_run_lanes):
            self.assertEqual(0, graph_goal.command_run(args))
        self.assertEqual([], started_lanes)                            # no task started
        self.assertTrue((root / "campaign" / "stop.flag").exists())    # not silently dropped
        kinds = [row["kind"] for row in _events(root)]
        self.assertIn("stop_requested", kinds)    # the flag's own placement stayed on record
        self.assertNotIn("stop_cleared", kinds)   # no clearing fabricated


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
