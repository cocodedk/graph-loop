"""An account the doctor cannot sign in is retired before any card is claimed."""

import json
import os
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import accounts
import model_router
import resources
import tmp_root  # noqa: F401 — isolate every temporary file
import yaml
from backlog import Backlog
from doctor_auth import run_accounts
from loop_steps_route import routed_build
from loop_types import TaskOutcome
from providers import Outcome
from test_driver import graph_goal
from turn import replan_pending
from workspace import Workspace


class RetiredAccounts(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.homes = [self.root / name for name in ("expired", "ready")]
        for home in self.homes:
            home.mkdir()
        self.credentials(0)
        self.credentials(1, refreshToken="test-refresh")
        self.env = mock.patch.dict(os.environ, {
            "GRAPH_ACCOUNTS": f"expired={self.homes[0]},ready={self.homes[1]}",
            "GRAPH_ROUTER": "off"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.path = self.root / "backlog.yaml"
        self.path.write_text(yaml.safe_dump({"tasks": [
            {"id": f"T{i}", "status": "todo", "goal": "g", "needs": [],
             "files": [f"a{i}.py"], "gate": "false", "done_when": "d"}
            for i in range(3)]}))
        self.book = Backlog(self.path)
        self.space = Workspace(self.root / "campaign").init(goal="g", backlog=str(self.path))
        (self.space.root / "approved").touch()

    def credentials(self, index, **fields):
        (self.homes[index] / ".credentials.json").write_text(
            json.dumps({"claudeAiOauth": {"expiresAt": 0, **fields}}))

    def alerts(self):
        return [row for row in self.space.events() if row["kind"] == "alert"]

    def drive(self, dry_run=False):
        chosen = []

        def run(task):
            chosen.append(model_router.choose(task, "build").resource.account)
            self.book.set_status(task["id"], "done")
            return TaskOutcome("done")

        args = SimpleNamespace(dry_run=dry_run, lanes=1, max_tasks=3)
        with mock.patch.object(graph_goal, "_space", return_value=self.space), \
                mock.patch.object(self.space, "only_driver"), \
                mock.patch.object(graph_goal, "Loop", return_value=SimpleNamespace(run_task=run)), \
                mock.patch.object(graph_goal, "before_turn"), \
                mock.patch.object(graph_goal, "after_lanes"), \
                mock.patch.object(graph_goal, "turn_opens", return_value=None) as opens:
            code = graph_goal.command_run(args)
        return code, chosen, opens.call_count

    def test_every_belt_and_router_excludes_the_retired_account(self):
        with run_accounts(self.space):
            for job in ("build", "plan", "review", "decide"):
                self.assertNotIn("expired", [one.account for one in resources.belt(job)])
            choice = model_router.choose({}, "build")
            self.assertEqual("ready", choice.resource.account)
            _, belt = routed_build(SimpleNamespace(space=self.space), {"id": "T1"})
            self.assertEqual({"ready"}, {one.account for one in belt})
            # Signing in during a run does not change its fixed retirement set.
            self.credentials(0, refreshToken="renewed")
            self.assertEqual(("ready",), accounts.available())

    def test_lanes_only_route_the_remaining_account_and_alert_once_across_turns(self):
        code, chosen, turns = self.drive()
        self.assertEqual((0, ["ready"] * 3, 3), (code, chosen, turns))
        [alert] = self.alerts()
        self.assertIn("expired", alert["why"])
        self.assertIn(f"CLAUDE_CONFIG_DIR={self.homes[0]} claude /login", alert["why"])
        rows = list(self.space.events())
        self.assertLess(next(i for i, r in enumerate(rows) if r["kind"] == "alert"),
                        next(i for i, r in enumerate(rows) if r["kind"] == "claimed"))

    def test_replanner_only_calls_the_remaining_account(self):
        self.book.set_status("T0", "refused_contract", refused_why="too broad")
        planner = mock.Mock(return_value=Outcome("ok", text=json.dumps({
            "goal": "a better goal", "files": ["a0.py"], "done_when": "proof"})))
        with run_accounts(self.space):
            self.assertTrue(replan_pending(self.book, self.space, planner))
        self.assertEqual(["ready"], [call.args[1].account for call in planner.call_args_list])
        self.assertEqual("todo", self.book.task("T0")["status"])

    def test_no_accounts_stops_before_a_turn_or_claim_with_one_alert(self):
        self.credentials(1)
        self.assertEqual((1, [], 0), self.drive())
        [alert] = self.alerts()
        self.assertIn("expired", alert["why"])
        self.assertIn("ready", alert["why"])
        [written] = self.space.alerts()
        self.assertEqual(2, written.count("claude /login"))
        self.assertFalse(any(row["kind"] == "claimed" for row in self.space.events()))
        self.assertEqual(["todo"] * 3, [task["status"] for task in self.book.tasks()])
        self.assertEqual("driver_stood_down", list(self.space.events())[-1]["kind"])

    def test_retirement_ends_with_the_run_even_if_it_raises(self):
        with self.assertRaisesRegex(RuntimeError, "stopped"), run_accounts(self.space):
            raise RuntimeError("stopped")
        self.assertEqual(accounts.names(), accounts.available())
        self.credentials(0, refreshToken="renewed")
        with run_accounts(self.space) as remaining:
            self.assertEqual(accounts.names(), remaining)
        self.assertEqual(1, len(self.alerts()))

    def test_dry_run_does_not_retire_or_alert(self):
        self.credentials(1)
        self.assertEqual((0, [], 1), self.drive(dry_run=True))
        self.assertEqual([], self.alerts())
        self.assertEqual(accounts.names(), accounts.available())


if __name__ == "__main__":
    unittest.main()
