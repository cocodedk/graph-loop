"""Taking `refs/heads/` off a branch name takes only the leading one.

`split("refs/heads/")[-1]` cut a name that CONTAINS the prefix as well:
`campaign/refs/heads/fresh` became `fresh`, another branch entirely — created
by `init`, named on the pending-keep note, pushed, and moved by the keeper
(an independent review). Five readings did it; there is one now, `keep_branch.plain`.
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
import keep_pending
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper
from keep_branch import plain
from test_keep import repo

EXPECTED_TESTS = 5
EMBEDDED = "campaign/refs/heads/fresh"
DEEP = "refs/heads/fresh"        # a branch actually called that


class PlainNameTest(unittest.TestCase):
    def test_only_a_leading_prefix_comes_off(self):
        self.assertEqual("campaign/fresh", plain("refs/heads/campaign/fresh"))
        self.assertEqual(EMBEDDED, plain(EMBEDDED))
        self.assertEqual(EMBEDDED, plain(f"refs/heads/{EMBEDDED}"))


class InitMakesTheNamedBranchTest(unittest.TestCase):
    def test_init_creates_the_branch_the_campaign_asked_for(self):
        root = repo()
        backlog = pathlib.Path(root) / "backlog.yaml"
        backlog.write_text(yaml.safe_dump({"tasks": [
            {"id": "T1", "goal": "g", "files": ["a.py"], "gate": "true",
             "done_when": "x", "status": "todo"}]}), "utf-8")
        camp = pathlib.Path(tempfile.mkdtemp()) / "campaign"
        done = subprocess.run(
            (sys.executable, str(DRIVE / "drive-goal.py"), "init",
             "--backlog", str(backlog), "--goal", "prove it"),
            env=dict(os.environ, DRIVE_REPO=str(root), DRIVE_CAMPAIGN=str(camp),
                     DRIVE_BRANCH=EMBEDDED),
            check=False, capture_output=True, text=True)
        self.assertEqual(0, done.returncode, done.stderr)
        refs = subprocess.run(("git", "-C", root, "for-each-ref", "--format=%(refname)",
                               "refs/heads"), capture_output=True, text=True,
                              check=True).stdout.split()
        self.assertIn(f"refs/heads/{EMBEDDED}", refs)
        self.assertNotIn("refs/heads/fresh", refs)


class RecordedNameSurvivesTest(unittest.TestCase):
    """What `init` records is read again by the keeper, which normalizes it
    once more — so the recorded spelling has to survive that reading.

    `refs/heads/refs/heads/fresh` is the full ref of a branch actually called
    `refs/heads/fresh`. Recording the plain name gave the keeper `fresh` back,
    and the first keep died three times on a ref nothing had created (Codex on
    c36d8752). The qualified ref is what survives: taking the prefix off and
    putting it back is the same ref again.
    """

    def test_a_keep_lands_where_init_said_it_would(self):
        root = repo()
        backlog = pathlib.Path(root) / "backlog.yaml"
        backlog.write_text(yaml.safe_dump({"tasks": [
            {"id": "T1", "goal": "g", "files": ["a.py"], "gate": "true",
             "done_when": "x", "status": "todo"}]}), "utf-8")
        camp = pathlib.Path(tempfile.mkdtemp()) / "campaign"
        done = subprocess.run(
            (sys.executable, str(DRIVE / "drive-goal.py"), "init",
             "--backlog", str(backlog), "--goal", "prove it"),
            env=dict(os.environ, DRIVE_REPO=str(root), DRIVE_CAMPAIGN=str(camp),
                     DRIVE_BRANCH=f"refs/heads/{DEEP}"),
            check=False, capture_output=True, text=True)
        self.assertEqual(0, done.returncode, done.stderr)
        recorded = json.loads((camp / "events.jsonl").read_text("utf-8").splitlines()[0])
        keeper = Keeper(root, recorded["branch"])
        tree = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", tree,
                        keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(tree) / "a.py").write_text("two\n")
        commit = keeper.keep("T1", tree, "made it two")
        landed = subprocess.run(("git", "-C", root, "rev-parse", f"refs/heads/{DEEP}"),
                                capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(commit, landed)


class NoteNameTest(unittest.TestCase):
    def test_the_pending_note_names_the_whole_branch(self):
        """The note is how a keep already written is found again: a name that
        collapses to `fresh` cannot tell two campaigns apart."""
        root = repo()
        note = keep_pending.note_path(root, EMBEDDED, "T1")
        self.assertIn("fresh", note.name)
        self.assertEqual(note, keep_pending.note_path(root, f"refs/heads/{EMBEDDED}", "T1"))
        self.assertNotEqual(note, keep_pending.note_path(root, "fresh", "T1"))


class KeeperMovesTheNamedBranchTest(unittest.TestCase):
    def test_a_keep_lands_on_the_branch_the_campaign_named(self):
        root = repo()
        subprocess.run(("git", "-C", root, "branch", EMBEDDED, "HEAD"),
                       capture_output=True, check=True)
        keeper = Keeper(root, EMBEDDED)
        tree = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", tree,
                        keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(tree) / "a.py").write_text("two\n")
        commit = keeper.keep("T1", tree, "made it two")
        landed = subprocess.run(("git", "-C", root, "rev-parse", f"refs/heads/{EMBEDDED}"),
                                capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(commit, landed)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
