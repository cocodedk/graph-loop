"""One driver per campaign, whoever started it.

astra's review, finding 7: `supervisor.sh` takes `supervisor.lock` with
`flock -n`, so two supervisors can never double up — but a driver started by
hand takes no lock at all, and two drivers on one campaign write over each
other's claims. A refused driver must also announce nothing: the board reads
the `driver_started` event as the driver's identity.
"""

from __future__ import annotations

import fcntl
import importlib.util
import pathlib
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

_spec = importlib.util.spec_from_file_location("drive_goal", HERE / "drive-goal.py")
assert _spec is not None and _spec.loader is not None
drive_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drive_goal)

EXPECTED_TESTS = 2


def campaign(root: pathlib.Path) -> Workspace:
    """An approved campaign on an empty backlog: `run` reaches its first turn."""
    backlog = root / "b.yaml"
    backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": []}))
    space = Workspace(root / "campaign").init(goal="the backlog", backlog=str(backlog))
    (space.root / "approved").write_text("approved\n", "utf-8")
    return space


def args_for(space: Workspace, dry_run: bool = False) -> types.SimpleNamespace:
    return types.SimpleNamespace(workspace=str(space.root), dry_run=dry_run,
                                 lanes=3, max_tasks=0,
                                 idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)


def run(args) -> int:
    """`command_run` with nothing that would reach the real repository."""
    with unittest.mock.patch.object(Keeper, "pending", lambda self: []), \
         unittest.mock.patch.object(drive_goal, "turn_opens", lambda *a: None), \
         unittest.mock.patch("publishing.behind", return_value=False):
        return drive_goal.command_run(args)


class DriverLockTest(unittest.TestCase):
    def test_a_second_driver_on_one_campaign_refuses_and_announces_nothing(self):
        space = campaign(pathlib.Path(tempfile.mkdtemp()))
        with open(space.root / "driver.lock", "w") as held:   # the driver already running
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(SystemExit) as refused:
                run(args_for(space))

        self.assertIn("driver", str(refused.exception))
        self.assertEqual([], [row for row in space.events()
                              if row.get("kind") == "driver_started"])

    def test_a_dry_run_takes_no_lock_and_never_waits_for_the_driver(self):
        """A dry run reads and writes nothing, so it must not be kept out of a
        campaign a driver is working — nor keep the next driver out itself."""
        space = campaign(pathlib.Path(tempfile.mkdtemp()))
        with open(space.root / "driver.lock", "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(0, run(args_for(space, dry_run=True)))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
