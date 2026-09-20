"""The watchdog's quarantine write, run through the real driver: a card that
finished between the watchdog's read and this write must stay finished.

Split out as a new file rather than added to `test_driver.py`, already at its
own 200-line cap.
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
from watchdog import Verdict

# Loaded by path, once, so this test can monkeypatch the exact names
# `command_run`'s loop body calls — same approach as `test_driver.py`, in its
# own module so the two patch each other's copy of nothing. The watchdog itself
# is read where the reading lives now (`lib/driver_turn.after_lanes`).
_spec = importlib.util.spec_from_file_location("drive_goal_quarantine", HERE / "drive-goal.py")
assert _spec is not None and _spec.loader is not None
drive_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drive_goal)

EXPECTED_TESTS = 3


def _campaign(tasks: list[dict]) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp())
    backlog = root / "b.yaml"
    backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": tasks}))
    env = {**os.environ, "DRIVE_REPO": str(HERE.parents[1]), "DRIVE_CAMPAIGN": str(root / "campaign"),
          "DRIVE_BACKLOG": str(backlog)}
    init = subprocess.run([sys.executable, str(HERE / "drive-goal.py"), "init",
                           "--backlog", str(backlog), "--branch", "campaign/test-quarantine"],
                          capture_output=True, text=True, env=env, check=False)
    assert init.returncode == 0, init.stdout + init.stderr
    (root / "campaign" / "approved").write_text("test")
    return root


def _events(root: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in (root / "campaign" / "events.jsonl").read_text().splitlines()
           if line.strip()]


def _run_spinning_on(status: str, needs: list[str] | None = None,
                     extra: list[dict] | None = None) -> tuple[str, list[dict], list[dict]]:
    """Run `command_run` with T1 already `status` while the watchdog still
    names it spinning. Returns T1's status after the run, any quarantine
    events, and any spin_spent events — done and dropped settle
    (`backlog_status.settled`); a fresh slice does not, its atom still open,
    yet all three must stay put, and each must still spend the spin truthfully."""
    root = _campaign([
        {"id": "T1", "goal": "already finished", "status": status,
         "needs": needs or [], "files": []},
        {"id": "T2", "goal": "startable", "status": "todo", "needs": [], "files": []},
        *(extra or []),
    ])
    args = types.SimpleNamespace(workspace=str(root / "campaign"), dry_run=False,
                                 lanes=3, max_tasks=1,
                                 idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)
    verdict = Verdict(spinning=True, task="T1", why="T1 ended at gate the same way twice")
    with unittest.mock.patch.object(Keeper, "pending", lambda self: []), \
         unittest.mock.patch("publishing.behind", return_value=False), \
         unittest.mock.patch.object(drive_goal, "run_lanes", lambda *a, **k: (1, False)), \
         unittest.mock.patch("driver_turn.watchdog_check", lambda *a, **k: verdict):
        assert drive_goal.command_run(args) == 0
    t1 = next(row for row in yaml.safe_load((root / "b.yaml").read_text())["tasks"]
             if row["id"] == "T1")
    events = _events(root)
    return (t1["status"], [row for row in events if row.get("kind") == "quarantined"],
           [row for row in events if row.get("kind") == "spin_spent"])


class QuarantineDoneGuardTest(unittest.TestCase):
    def test_a_card_already_done_stays_done_and_is_not_quarantined(self):
        # T1 finished (another driver's write) between the watchdog's read and
        # this one's quarantine write: the spinning verdict still names it,
        # but the card must stay done and no quarantine event overwrites it.
        status, quarantines, spin_spent = _run_spinning_on("done")
        self.assertEqual("done", status)
        self.assertEqual([], quarantines)
        self.assertEqual(["T1"], [row.get("task") for row in spin_spent])

    def test_a_card_already_dropped_stays_dropped_and_is_not_quarantined(self):
        # Same race, the other settled ending: T1 was decided against, not
        # finished — settled() must cover "dropped" too, or a card the loop
        # will never touch again gets quarantined instead of staying dropped.
        status, quarantines, spin_spent = _run_spinning_on("dropped")
        self.assertEqual("dropped", status)
        self.assertEqual([], quarantines)
        self.assertEqual(["T1"], [row.get("task") for row in spin_spent])

    def test_a_card_freshly_sliced_with_an_open_atom_stays_sliced_and_is_not_quarantined(self):
        # Same race, a third ending that is not settled at all: T1 was sliced
        # into T1.1 a moment before this write, and T1.1 is still "todo", so
        # settled() does not call T1 finished — but "sliced" must never be
        # overwritten either, or the atom is orphaned from a parent that no
        # longer says it was cut.
        status, quarantines, spin_spent = _run_spinning_on(
            "sliced", needs=["T1.1"],
            extra=[{"id": "T1.1", "goal": "the open atom", "status": "todo",
                   "needs": [], "files": []}])
        self.assertEqual("sliced", status)
        self.assertEqual([], quarantines)
        self.assertEqual(["T1"], [row.get("task") for row in spin_spent])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
