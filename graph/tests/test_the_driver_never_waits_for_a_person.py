"""The driver keeps going by itself, and `--keep-going` is gone.

Six campaigns, and not one finished without somebody restarting the driver.
The flag was half of why: off, the driver stood down the moment nothing was
startable, which on a run of four cards is the first card that parks. On is
not a default either — CLAUDE.md § Code says the loop never waits for a
person, and a flag that can be left off is a way for it to.

So there is one behaviour, and it is neither of the old two. A fault outside
the tasks — a usage limit, an expired account, a provider down — resets with
nobody doing anything, so the loop waits for it, for as long as it takes.
Nothing startable is the opposite: a parked card's next actor is the plan
phase, a different command, so no amount of waiting moves it and the driver
hands back to the supervisor. In between is the one case worth waiting on:
another agent holds a claim, and what it finishes can release a dependency.
"""

from __future__ import annotations

import collections
import importlib.util
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE / "lib"))
from cli_args import build_parser
from workspace import Workspace

_spec = importlib.util.spec_from_file_location("graph_goal", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 5
PARKED = {"id": "T1", "status": "needs_slice", "files": ["a.py"], "gate": "false",
          "goal": "the card nothing will offer again"}


def held(space: Workspace) -> None:
    """A claim another agent holds, alive because this process's group is."""
    space.claim("T2", pgid=os.getpgid(0), account="work", worktree="")


def campaign(root: pathlib.Path, task: dict) -> types.SimpleNamespace:
    backlog = root / "b.yaml"
    backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": [task]}), "utf-8")
    space = Workspace(root / "campaign")
    space.init(goal="a campaign", backlog=str(backlog), branch="")
    (space.root / "approved").write_text("test", "utf-8")
    return types.SimpleNamespace(workspace=str(space.root), dry_run=False, lanes=3,
                                 max_tasks=0, idle_seconds=0, attempt_ceiling=12,
                                 hours_ceiling=2.0)


class TheFlagIsGone(unittest.TestCase):
    def test_run_no_longer_takes_keep_going(self):
        # Every subcommand answers None, so a command added beside `run`
        # never has to be listed here for this to go on saying what it says.
        parser = build_parser("graph", collections.defaultdict(lambda: None))
        with self.assertRaises(SystemExit):
            parser.parse_args(["run", "--keep-going"])
        self.assertEqual(3, parser.parse_args(["run"]).lanes)   # the rest of `run` still parses


class TheDriverDecidesForItself(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.args = campaign(self.root, PARKED)
        self.space = Workspace(pathlib.Path(self.args.workspace))

    def test_a_parked_queue_with_nobody_working_hands_back(self):
        """No flag decides it now: nothing can start, nobody holds a claim, so
        nothing here becomes startable by waiting."""
        with mock.patch.object(Workspace, "idle",
                               side_effect=AssertionError("idled on a queue that cannot move")):
            code = graph_goal.command_run(self.args)
        self.assertNotEqual(0, code)   # not finished: the supervisor starts another driver
        stood = [row for row in self.space.events() if row.get("kind") == "driver_stood_down"]
        self.assertEqual(1, len(stood))
        self.assertIn("nothing startable", stood[0]["why"])

    def test_a_claim_another_agent_holds_is_worth_waiting_for(self):
        """The one case waiting helps: what it finishes can release a card
        here. The driver idles instead of ending, and says who it waits on."""
        held(self.space)
        rounds = []

        def stop(space, seconds):        # one wait, then the stop flag ends the run
            rounds.append(seconds)
            (self.space.root / "stop.flag").write_text("stop", "utf-8")

        with mock.patch.object(Workspace, "idle", stop):
            graph_goal.command_run(self.args)
        self.assertEqual(1, len(rounds))
        idled = [row for row in self.space.events() if row.get("kind") == "idle"]
        self.assertEqual(["T2"], idled[0]["running"])
        self.assertEqual(["T1"], idled[0]["unfinished"])

    def test_a_finished_campaign_never_idles_on_a_claim(self):
        """Nothing unfinished ends the campaign whoever else is working: the
        wait above is about a card here, and there is none."""
        self.args = campaign(pathlib.Path(tempfile.mkdtemp()),
                             {**PARKED, "status": "done"})
        held(Workspace(pathlib.Path(self.args.workspace)))
        with mock.patch.object(Workspace, "idle",
                               side_effect=AssertionError("idled with nothing unfinished")):
            graph_goal.command_run(self.args)

    def test_a_dry_run_still_says_what_it_would_do_and_writes_nothing(self):
        self.args.dry_run = True
        with mock.patch.object(Workspace, "idle",
                               side_effect=AssertionError("a dry run waited")):
            self.assertEqual(0, graph_goal.command_run(self.args))
        self.assertEqual([], [row for row in self.space.events()
                              if row.get("kind") == "driver_stood_down"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
