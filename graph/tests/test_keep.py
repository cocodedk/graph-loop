"""Accepted work is kept: committed on a campaign branch, and inherited by the next task.

Written before `keep.py`. The first driver left every accepted change in a
temporary worktree — a reboot would have erased the weekend, and the next task's
worktree, cut from the old HEAD, would have built without its dependency.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper

EXPECTED_TESTS = 13


def repo() -> str:
    root = tempfile.mkdtemp()
    for args in (("git", "init", "-q", "-b", "main"),
                 ("git", "config", "user.email", "t@example.test"),
                 ("git", "config", "user.name", "test")):
        subprocess.run(args, cwd=root, capture_output=True, check=True)
    (pathlib.Path(root) / "a.py").write_text("one\n")
    subprocess.run(("git", "add", "-A"), cwd=root, capture_output=True, check=True)
    subprocess.run(("git", "commit", "-qm", "first"), cwd=root, capture_output=True,
                   check=True)
    return root


def sha(root: str, ref: str = "HEAD") -> str:
    return subprocess.run(("git", "-C", root, "rev-parse", ref), capture_output=True,
                          text=True, check=True).stdout.strip()


def branch_files(root: str, branch: str) -> str:
    return subprocess.run(("git", "-C", root, "show", f"{branch}:a.py"),
                          capture_output=True, text=True, check=True).stdout


class KeepTest(unittest.TestCase):
    def setUp(self):
        self.root = repo()
        self.keeper = Keeper(self.root, "campaign/test")

    def _worktree(self, task_id: str, text: str) -> str:
        path = str(pathlib.Path(tempfile.mkdtemp()) / task_id)
        subprocess.run(("git", "-C", self.root, "worktree", "add", "-q", "--detach",
                        path, self.keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(path) / "a.py").write_text(text)
        return path

    def test_accepted_work_becomes_a_commit_on_the_campaign_branch(self):
        commit = self.keeper.keep("T1", self._worktree("T1", "two\n"), "made it two")
        self.assertTrue(commit)
        self.assertEqual("two\n", branch_files(self.root, "campaign/test"))
        self.assertIn("T1", subprocess.run(
            ("git", "-C", self.root, "log", "-1", "--format=%s", "campaign/test"),
            capture_output=True, text=True, check=True).stdout)

    def test_the_branch_starts_from_the_main_line_and_never_moves_it(self):
        before = sha(self.root, "main")
        self.keeper.keep("T1", self._worktree("T1", "two\n"), "made it two")
        self.assertEqual(before, sha(self.root, "main"))

    def test_the_next_task_starts_from_the_last_accepted_work(self):
        self.keeper.keep("T1", self._worktree("T1", "two\n"), "made it two")
        second = self._worktree("T2", "two\nthree\n")   # cut from the new tip
        self.assertEqual("two\n", (pathlib.Path(second) / "a.py").read_text()[:4])
        self.keeper.keep("T2", second, "added three")
        self.assertEqual("two\nthree\n", branch_files(self.root, "campaign/test"))

    def test_a_worktree_with_nothing_changed_is_not_committed(self):
        commit = self.keeper.keep("T1", self._worktree("T1", "one\n"), "changed nothing")
        self.assertIsNone(commit)

    def test_the_tip_is_the_branch_when_it_exists_and_the_head_before_that(self):
        self.assertEqual(sha(self.root, "HEAD"), self.keeper.tip())
        self.keeper.keep("T1", self._worktree("T1", "two\n"), "made it two")
        self.assertEqual(sha(self.root, "campaign/test"), self.keeper.tip())

    def test_a_split_that_renames_its_own_file_still_commits(self):
        # `git add -- a.py` on a path the builder deleted (a rename to a_part.py)
        # failed the whole commit, so an accepted split landed nothing.
        path = self._worktree("T1", "two\n")
        (pathlib.Path(path) / "a.py").unlink()
        (pathlib.Path(path) / "a_part.py").write_text("two\n")
        commit = self.keeper.keep("T1", path, "split it", files=["a.py", "a_part.py"])
        self.assertTrue(commit)
        listing = subprocess.run(("git", "-C", self.root, "ls-tree", "--name-only",
                                  "campaign/test"), capture_output=True, text=True,
                                 check=True).stdout
        self.assertIn("a_part.py", listing)
        self.assertNotIn("a.py\n", listing)

    def test_only_the_files_the_task_owned_are_committed(self):
        path = self._worktree("T1", "two\n")
        (pathlib.Path(path) / "stray.py").write_text("not mine\n")
        self.keeper.keep("T1", path, "made it two", files=["a.py"])
        listing = subprocess.run(("git", "-C", self.root, "ls-tree", "--name-only",
                                  "campaign/test"), capture_output=True, text=True,
                                 check=True).stdout
        self.assertIn("a.py", listing)
        self.assertNotIn("stray.py", listing)

    def test_push_sends_the_branch_to_the_configured_remote(self):
        bare = tempfile.mkdtemp()
        subprocess.run(("git", "init", "-q", "--bare", bare), capture_output=True, check=True)
        subprocess.run(("git", "-C", self.root, "remote", "add", "origin", bare),
                       capture_output=True, check=True)
        commit = self.keeper.keep("T1", self._worktree("T1", "two\n"), "made it two")
        self.assertEqual("", self.keeper.push())
        self.assertEqual(commit, sha(bare, "campaign/test"))

    def test_push_with_no_remote_fails_without_raising(self):
        commit = self.keeper.keep("T1", self._worktree("T1", "two\n"), "made it two")
        failed = self.keeper.push()
        self.assertTrue(failed)
        self.assertEqual(commit, sha(self.root, "campaign/test"))

    def test_a_lost_record_leaves_a_note_pending_until_settled(self):
        # `record` marks the card done; a crash (or, here, an exception) right
        # after the branch moved must not lose the fact that it did.
        path = self._worktree("T1", "two\n")
        with self.assertRaises(ZeroDivisionError):
            self.keeper.keep("T1", path, "made it two", record=lambda sha: 1 / 0)
        note = pathlib.Path(self.root) / ".git" / "keep-pending-campaign%2Ftest-T1"
        self.assertTrue(note.exists())
        branch_sha = sha(self.root, "campaign/test")
        self.assertEqual([("T1", branch_sha)], self.keeper.pending())
        self.assertTrue(note.exists())                                  # reading alone never settles it
        self.assertEqual([("T1", branch_sha)], self.keeper.pending())   # idempotent: same pair again
        self.keeper.settle("T1")
        self.assertFalse(note.exists())
        self.assertEqual([], self.keeper.pending())

    def test_a_slash_branch_and_its_underscore_twin_keep_separate_notes(self):
        other = Keeper(self.root, "campaign_test")   # old encoding aliased this with "campaign/test"
        with self.assertRaises(ZeroDivisionError):
            self.keeper.keep("T1", self._worktree("T1", "two\n"), "on test",
                             record=lambda sha: 1 / 0)
        other_path = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", self.root, "worktree", "add", "-q", "--detach",
                        other_path, other.tip()), capture_output=True, check=True)
        (pathlib.Path(other_path) / "a.py").write_text("three\n")
        with self.assertRaises(ZeroDivisionError):
            other.keep("T1", other_path, "on other", record=lambda sha: 1 / 0)
        self.assertEqual([("T1", sha(self.root, "campaign/test"))], self.keeper.pending())
        self.assertEqual([("T1", sha(self.root, "campaign_test"))], other.pending())


class StaleBaseTest(unittest.TestCase):
    """The race that orphaned T1: a keep from a worktree cut before another
    task's keep must not discard that keep — the commit is built on the
    branch's current tip, whatever the worktree's base was."""

    def test_a_keep_from_a_stale_base_keeps_the_other_tasks_commit(self):
        root = repo()
        keeper = Keeper(root, "campaign/test")
        early = str(pathlib.Path(tempfile.mkdtemp()) / "T-early")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach",
                        early, keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(early) / "b.py").write_text("early task file\n")
        first = keeper.keep("T-mid", _fresh(root, keeper, "a.py", "two\n"),
                            "kept while early was still building")
        kept = keeper.keep("T-early", early, "finished on a stale base",
                           files=["b.py"])
        self.assertTrue(first and kept)
        log = subprocess.run(("git", "-C", root, "log", "--format=%s",
                              "campaign/test"), capture_output=True, text=True,
                             check=True).stdout
        self.assertIn("T-mid", log)
        self.assertIn("T-early", log)
        self.assertEqual("two\n", branch_files(root, "campaign/test"))


def _fresh(root, keeper, name, text):
    path = str(pathlib.Path(tempfile.mkdtemp()) / "mid")
    subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach",
                    path, keeper.tip()), capture_output=True, check=True)
    (pathlib.Path(path) / name).write_text(text)
    return path



class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
