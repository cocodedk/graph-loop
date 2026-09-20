"""The driver itself, run as a process on a throwaway campaign: what it
writes at start is what the board reads."""

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

from contract import revision
from keep import Keeper

# `graph-goal.py` (hyphenated, not an importable name) loaded by path, once,
# so a test can monkeypatch the exact `turn_opens` name its loop body calls.
_spec = importlib.util.spec_from_file_location("graph_goal", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 6


def campaign(root: pathlib.Path) -> dict:
    backlog = root / "b.yaml"
    backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": []}))
    env = {**os.environ, "GRAPH_REPO": str(HERE.parents[1]), "GRAPH_CAMPAIGN": str(root / "campaign"),
           "GRAPH_BACKLOG": str(backlog)}
    init = subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "init", "--backlog", str(backlog)],
                          capture_output=True, text=True, env=env, check=False)
    assert init.returncode == 0, init.stdout + init.stderr
    (root / "campaign" / "approved").write_text("test")
    return env


def events(root: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in (root / "campaign" / "events.jsonl").read_text().splitlines() if line.strip()]


class DriverStartTest(unittest.TestCase):
    def test_the_driver_announces_itself_with_its_identity_before_its_first_turn(self):
        root = pathlib.Path(tempfile.mkdtemp()); env = campaign(root)
        run = subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "run"],
                             capture_output=True, text=True, env=env, check=False, timeout=120)
        started = [row for row in events(root) if row.get("kind") == "driver_started"]
        self.assertEqual(1, len(started), run.stdout + run.stderr)
        self.assertTrue(int(started[0].get("pid") or 0) > 0)
        self.assertIn(":", str(started[0].get("started") or ""))   # boot id and start tick, as a claim records them

    def test_a_dry_run_announces_nothing_and_leaves_the_restart_flag(self):
        root = pathlib.Path(tempfile.mkdtemp()); env = campaign(root)
        (root / "campaign" / "restart.flag").touch()
        (root / "campaign" / "stop.flag").write_text("stop")
        subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "run", "--dry-run"],
                       capture_output=True, text=True, env=env, check=False, timeout=120)
        self.assertEqual([], [row for row in events(root) if row.get("kind") == "driver_started"])
        self.assertTrue((root / "campaign" / "restart.flag").exists())   # not this process's to consume
        self.assertTrue((root / "campaign" / "stop.flag").exists())      # and no stop of a campaign cancelled

    def _pending_keep(self) -> tuple[pathlib.Path, pathlib.Path, str]:
        """A verified pending note (the keeper's own repo, not the campaign's): the
        branch already holds T1's commit, but the `record` call that would write
        its card crashed first. Returns (repo, note path, the commit the branch holds)."""
        repo = pathlib.Path(tempfile.mkdtemp())
        for git_args in (("git", "init", "-q", "-b", "main"),
                         ("git", "config", "user.email", "t@example.test"),
                         ("git", "config", "user.name", "test")):
            subprocess.run(git_args, cwd=repo, capture_output=True, check=True)
        (repo / "a.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=repo, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=repo, capture_output=True, check=True)
        keeper = Keeper(str(repo), "campaign/test")
        worktree = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", str(repo), "worktree", "add", "-q", "--detach",
                        worktree, keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(worktree) / "a.py").write_text("two\n")
        with self.assertRaises(ZeroDivisionError):
            keeper.keep("T1", worktree, "made it two", record=lambda commit: 1 / 0)
        note = pathlib.Path(repo, ".git", "keep-pending-campaign%2Ftest-T1")
        self.assertTrue(note.exists())
        return repo, note, keeper.tip()

    def _campaign_on(self, repo: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, dict]:
        """A campaign whose single task T1 is `todo`, on `repo`'s `campaign/test`.

        The card carries the revision its pending keep was made at: `_pending_keep`
        calls `Keeper.keep` alone, and the loop (`loop_judge._keep`) is what writes
        `keep_revision` — without it the note is unbound, which reconcile refuses
        the way it refuses a mismatch. The fixture was missing it, not the rule.
        """
        root = pathlib.Path(tempfile.mkdtemp())
        backlog = root / "b.yaml"
        card = {"id": "T1", "goal": "placeholder", "status": "todo", "needs": [], "files": []}
        card["keep_revision"] = revision(card)
        backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": [card]}))
        env = {**os.environ, "GRAPH_REPO": str(repo), "GRAPH_CAMPAIGN": str(root / "campaign"),
              "GRAPH_BACKLOG": str(backlog)}
        init = subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "init",
                               "--backlog", str(backlog), "--branch", "campaign/test"],
                              capture_output=True, text=True, env=env, check=False)
        assert init.returncode == 0, init.stdout + init.stderr
        (root / "campaign" / "approved").write_text("test")
        return root, backlog, env

    def test_a_dry_run_does_not_reconcile_a_pending_keep(self):
        repo, note, _ = self._pending_keep()
        root, backlog, env = self._campaign_on(repo)
        run = subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "run", "--dry-run"],
                             capture_output=True, text=True, env=env, check=False, timeout=120)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        self.assertIn("would run T1", run.stdout)   # the turn reached past the guard, not a crash
        self.assertTrue(note.exists())               # untouched
        self.assertEqual([], [row for row in events(root) if row.get("kind") == "accepted"])
        self.assertEqual("todo", yaml.safe_load(backlog.read_text())["tasks"][0]["status"])

    def test_a_pending_keep_with_an_already_written_accepted_event_settles_once(self):
        # A third crash: an earlier reconcile wrote the "accepted" event for this
        # task+commit but died before `set_status`/`settle` — this run is real
        # and must not repeat it.
        repo, note, branch_sha = self._pending_keep()
        root, backlog, env = self._campaign_on(repo)
        document = yaml.safe_load(backlog.read_text())
        document["tasks"][0]["triage"] = "work"
        backlog.write_text(yaml.safe_dump(document, sort_keys=False))
        # The previous reconcile's own write: same task, same commit, a fixed "at"
        # this test can check was reused rather than replaced.
        with (root / "campaign" / "events.jsonl").open("a") as handle:
            handle.write(json.dumps(
                {"at": "2026-01-01T00:00:00Z", "kind": "accepted", "task": "T1", "commit": branch_sha,
                 "why": "the branch held this keep; its card-write was lost"}) + "\n")

        run = subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "run"],
                             capture_output=True, text=True, env=env, check=False, timeout=120)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        accepted = [row for row in events(root) if row.get("kind") == "accepted"
                   and row.get("task") == "T1" and row.get("commit") == branch_sha]
        self.assertEqual(1, len(accepted))                            # not written twice
        self.assertEqual("2026-01-01T00:00:00Z", accepted[0]["at"])   # the existing one, reused
        self.assertFalse(note.exists())
        row = yaml.safe_load(backlog.read_text())["tasks"][0]
        self.assertEqual("done", row["status"])
        self.assertEqual("2026-01-01T00:00:00Z", row["kept_at"])
        self.assertNotIn("triage", row)

    def test_a_reconciled_keep_with_no_remote_still_settles_but_alerts(self):
        # No "origin" on this repo: reconcile's push fails, but the card still
        # closes and the note still clears — a person is told to push it by hand.
        repo, note, _ = self._pending_keep()
        root, backlog, env = self._campaign_on(repo)
        run = subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "run"],
                             capture_output=True, text=True, env=env, check=False, timeout=120)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        self.assertFalse(note.exists())
        self.assertEqual("done", yaml.safe_load(backlog.read_text())["tasks"][0]["status"])
        alerts = [row for row in events(root) if row.get("kind") == "alert" and row.get("task") == "T1"]
        self.assertTrue(alerts, run.stdout + run.stderr)
        self.assertIn("not pushed", alerts[0]["why"])

    def test_reconcile_and_push_run_before_turn_opens(self):
        # The order the loop body calls them in: reconcile first, so a stale
        # card is never offered to turn_opens's triage/replan/slice.
        root = pathlib.Path(tempfile.mkdtemp()); campaign(root)
        args = types.SimpleNamespace(workspace=str(root / "campaign"), dry_run=False,
                                     lanes=3, max_tasks=0,
                                     idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)
        order: list[str] = []
        # In-process: `loop.keeper` is the real REPO this module was imported
        # against, so `behind` is patched out — this order check must never push.
        with unittest.mock.patch.object(Keeper, "pending", lambda self: order.append("pending") or []), \
             unittest.mock.patch.object(graph_goal, "turn_opens",
                                        lambda *a: order.append("turn_opens")), \
             unittest.mock.patch("publishing.behind", return_value=False):
            self.assertEqual(0, graph_goal.command_run(args))
        self.assertEqual(["pending", "turn_opens"], order)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
