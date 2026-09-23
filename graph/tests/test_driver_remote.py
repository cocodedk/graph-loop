"""The driver's turn-top reconcile, when the campaign branch itself is still
behind its remote — no task involved, only the push at the top of the turn.

Split out of `test_driver.py` (already at its own 200-line cap). Each test's
backlog is empty on purpose: nothing must ever become ready to run, so only
the turn-top reconcile is exercised, never the real builder.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_TESTS = 2


def _repo(branch: str = "campaign/test") -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp())
    for args in (("git", "init", "-q", "-b", "main"),
                 ("git", "config", "user.email", "t@example.test"),
                 ("git", "config", "user.name", "test")):
        subprocess.run(args, cwd=root, capture_output=True, check=True)
    (root / "a.py").write_text("one\n")
    subprocess.run(("git", "add", "-A"), cwd=root, capture_output=True, check=True)
    subprocess.run(("git", "commit", "-qm", "first"), cwd=root, capture_output=True, check=True)
    # The campaign branch exists, and no worktree holds it — the shape the real
    # repository is in, and the only one a keeper accepts (`keep_branch.py`).
    subprocess.run(("git", "-C", str(root), "branch", branch), capture_output=True, check=True)
    return root


def _campaign(repo: pathlib.Path) -> tuple[pathlib.Path, dict]:
    root = pathlib.Path(tempfile.mkdtemp())
    backlog = root / "b.yaml"
    backlog.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": []}))
    env = {**os.environ, "GRAPH_REPO": str(repo), "GRAPH_CAMPAIGN": str(root / "campaign"),
          "GRAPH_BACKLOG": str(backlog)}
    init = subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "init",
                           "--backlog", str(backlog), "--branch", "campaign/test"],
                          capture_output=True, text=True, env=env, check=False)
    assert init.returncode == 0, init.stdout + init.stderr
    (root / "campaign" / "approved").write_text("test")
    (root / "campaign" / "contact").write_text("person@example.test\n")
    return root, env


def _events(root: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in (root / "campaign" / "events.jsonl").read_text().splitlines() if line.strip()]


def _run(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HERE / "graph-goal.py"), "run"],
                          capture_output=True, text=True, env=env, check=False, timeout=120)


class TurnTopRemoteTest(unittest.TestCase):
    def test_a_turn_top_pushes_a_branch_still_ahead_of_its_remote(self):
        # A bare remote with nothing pushed to it yet: `campaign/test` is
        # ahead of it from the first commit on, exactly as a run that ended
        # right after its last keep — with no later keep to carry the push — leaves it.
        repo = _repo()
        bare = tempfile.mkdtemp()
        subprocess.run(("git", "init", "-q", "--bare", bare), capture_output=True, check=True)
        subprocess.run(("git", "-C", str(repo), "remote", "add", "origin", bare),
                       capture_output=True, check=True)
        root, env = _campaign(repo)
        run = _run(env)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        pushed = [row for row in _events(root) if row.get("kind") == "pushed"]
        self.assertTrue(pushed, run.stdout + run.stderr)   # checked first: a clean assertion, not a rev-parse crash
        local = subprocess.run(("git", "-C", str(repo), "rev-parse", "campaign/test"),
                               capture_output=True, text=True, check=True).stdout.strip()
        remote = subprocess.run(("git", "-C", bare, "rev-parse", "campaign/test"),
                                capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(local, remote)

    def test_a_behind_alert_is_written_once_not_twice_across_two_turn_tops(self):
        repo = _repo()   # no remote configured at all: the push fails the same way every time
        root, env = _campaign(repo)
        for _ in range(2):
            run = _run(env)
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        alerts = [row for row in _events(root) if row.get("kind") == "alert"
                 and "the branch has commits origin does not hold" in str(row.get("why", ""))]
        self.assertEqual(1, len(alerts), run.stdout + run.stderr)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
