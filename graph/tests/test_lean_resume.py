"""The lean loop across runs: a stopped spec carries on in its kept worktree, and
branches not merged into origin's main are found. Git is real; the rest is faked."""

import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_git
import lean_run
from test_lean_run import Rig


class Resume(Rig):
    def test_a_stopped_spec_carries_on_in_its_kept_worktree(self):
        self.run_it(self.builder(("ring.py", "grey\n"), ("ring.py", "grey1\n"), ("ring.py", "grey2\n")),
                    suites=(False, False, False))
        kept = next(row for row in self.ws.events() if row["kind"] == "lean_stopped")["tree"]
        self.assertIn("lean_status: stopped", self.spec.read_text())
        self.prompts.clear()
        url = self.run_it(self.builder(("ring.py", "amber\n")))
        self.assertTrue(url)
        started = [row for row in self.ws.events() if row["kind"] == "lean_feature_started"][-1]
        self.assertTrue(started["resumed"])
        self.assertEqual(kept, started["tree"])                 # the same checkout, not a new one
        self.assertIn("## Your last attempt failed", self.prompts[0])
        self.assertIn("FAILED: AmberTest > overdue", self.prompts[0])
        self.assertIn("lean_status: pr_open", self.spec.read_text())

    def test_a_kept_worktree_that_is_gone_starts_fresh(self):
        self.spec.write_text("---\nlean_status: stopped\nlean_worktree: /nowhere/at/all\n---\n"
                             "Show the overdue rest ring in amber.\n")
        self.run_it(self.builder(("ring.py", "amber\n")))
        started = next(row for row in self.ws.events() if row["kind"] == "lean_feature_started")
        self.assertFalse(started["resumed"])
        self.assertNotIn("last attempt failed", self.prompts[0])


class Cleanup(Rig):
    def test_a_tree_that_cannot_be_removed_never_loses_the_pull_request(self):
        denied = PermissionError(13, "Permission denied", "backend/__pycache__")
        with mock.patch.object(lean_run.Worktree, "remove", side_effect=denied):
            url = self.run_it(self.builder(("ring.py", "amber\n")))
        self.assertEqual("https://example.test/pull/1", url)
        left = next(row for row in self.ws.events() if row["kind"] == "lean_tree_left")
        self.assertIn("Permission denied", left["error"])


class Unmerged(Rig):
    def test_only_branches_not_merged_into_origin_main_are_listed(self):
        for name in ("merged", "waiting"):
            subprocess.run(("git", "-C", self.repo, "branch", name), check=True)
        (pathlib.Path(self.repo) / "b.py").write_text("two\n")
        subprocess.run(("git", "-C", self.repo, "switch", "-q", "waiting"), check=True)
        subprocess.run(("git", "-C", self.repo, "add", "b.py"), check=True)
        subprocess.run(("git", "-C", self.repo, "commit", "-qm", "unreviewed"), check=True)
        subprocess.run(("git", "-C", self.repo, "push", "-q", "origin", "merged", "waiting"),
                       capture_output=True, check=True)
        self.assertEqual(["origin/waiting"], lean_git.unmerged(self.repo))


if __name__ == "__main__":
    unittest.main()
