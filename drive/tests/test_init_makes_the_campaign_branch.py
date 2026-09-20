"""What `init` does about the branch the campaign will keep its work on.

It creates it at HEAD when the repository has not got it (astra's round-3
finding 9). Three things that reading has to get right, all found by Codex on
the first brick: a name written as a full ref must not become
`refs/heads/refs/heads/...`, which no keep can then move; a directory that is no
repository, or one with nothing committed yet, is not a failure — there is
simply nothing to branch from, and the campaign is still recorded; and a
repository that REFUSES the branch is a failure, said out loud rather than
swallowed.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

DRIVE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DRIVE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper
from test_keep import repo

EXPECTED_TESTS = 5
CARD = {"id": "T1", "goal": "g", "files": ["a.py"], "gate": "true",
        "done_when": "x", "status": "todo"}


class InitRig(unittest.TestCase):
    def init(self, root: str, branch: str) -> subprocess.CompletedProcess:
        """Run the real `drive-goal.py init` against this repository."""
        self.camp = pathlib.Path(tempfile.mkdtemp()) / "campaign"
        backlog = pathlib.Path(root) / "backlog.yaml"
        backlog.write_text(yaml.safe_dump({"tasks": [CARD]}), "utf-8")
        return subprocess.run(
            (sys.executable, str(DRIVE / "drive-goal.py"), "init",
             "--backlog", str(backlog), "--goal", "prove it"),
            env=dict(os.environ, DRIVE_REPO=str(root), DRIVE_CAMPAIGN=str(self.camp),
                     DRIVE_BRANCH=branch),
            check=False, capture_output=True, text=True)

    def recorded(self) -> str:
        """The branch the campaign wrote down — the FULL ref, so that reading it
        back and normalizing it again names the same branch (an independent review).
        """
        rows = [json.loads(line) for line in
                (self.camp / "events.jsonl").read_text("utf-8").splitlines()]
        return str(rows[0]["branch"])

    def refs(self, root: str) -> list[str]:
        return subprocess.run(("git", "-C", root, "for-each-ref", "--format=%(refname)",
                               "refs/heads"), capture_output=True, text=True,
                              check=True).stdout.split()


class FullRefNameTest(InitRig):
    def test_a_branch_written_as_a_full_ref_makes_that_ref_and_no_other(self):
        root = repo()
        self.assertEqual(0, self.init(root, "refs/heads/campaign/fresh").returncode)
        self.assertIn("refs/heads/campaign/fresh", self.refs(root))
        self.assertNotIn("refs/heads/refs/heads/campaign/fresh", self.refs(root))
        self.assertEqual("refs/heads/campaign/fresh", self.recorded())

    def test_the_first_keep_moves_the_branch_init_made(self):
        root = repo()
        self.init(root, "refs/heads/campaign/fresh")
        keeper = Keeper(root, self.recorded())
        tree = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", tree,
                        keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(tree) / "a.py").write_text("two\n")
        commit = keeper.keep("T1", tree, "made it two")
        self.assertEqual(commit, subprocess.run(
            ("git", "-C", root, "rev-parse", "refs/heads/campaign/fresh"),
            capture_output=True, text=True, check=True).stdout.strip())


class NothingToBranchFromTest(InitRig):
    def test_a_directory_that_is_no_repository_still_records_the_campaign(self):
        root = tempfile.mkdtemp()
        self.assertEqual(0, self.init(root, "campaign/fresh").returncode)
        self.assertEqual("refs/heads/campaign/fresh", self.recorded())

    def test_a_repository_with_nothing_committed_still_records_the_campaign(self):
        root = tempfile.mkdtemp()
        subprocess.run(("git", "-C", root, "init", "-q", "-b", "work"), check=True)
        self.assertEqual(0, self.init(root, "campaign/fresh").returncode)
        self.assertEqual("refs/heads/campaign/fresh", self.recorded())
        self.assertEqual([], self.refs(root))


class RefusedBranchTest(InitRig):
    def test_a_branch_the_repository_refuses_stops_init_and_says_why(self):
        root = repo()
        lock = pathlib.Path(root) / ".git" / "refs" / "heads" / "fresh.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("", "utf-8")           # another writer holds this ref
        done = self.init(root, "fresh")
        self.assertEqual(1, done.returncode, done.stdout)
        self.assertIn("cannot create fresh", done.stderr)
        self.assertNotIn("refs/heads/fresh", self.refs(root))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
