"""The keeper refuses a destination it must never move.

The branch is configurable — `init --branch`, `DRIVE_BRANCH` — so the loop can
be pointed at other work. Configured with `main`, the keeper's `update-ref`
moved the main line itself, against BLUEPRINT.md ("What it refuses to do: touch
the main branch") and README.md ("Accepted work goes to a campaign branch.
Never main, never force."). The same `update-ref` on a branch some worktree has
checked out leaves that tree's HEAD and index describing a commit it does not
hold.

A name is not the ref: `campaign/review` can be a symbolic ref to
`refs/heads/main`, and `update-ref` follows it. Nor is the answer durable: the
branch the keeper was made on can be checked out afterwards, so it is asked
again immediately before the local `update-ref`. A push does not move the local campaign branch
and is not refused for a checked-out destination.

Each case asserts the ref did not move: refusing after the work is published is
not refusing.
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

EXPECTED_TESTS = 7


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


def sha(root: str, ref: str) -> str:
    return subprocess.run(("git", "-C", root, "rev-parse", ref), capture_output=True,
                          text=True, check=True).stdout.strip()


class DestinationTest(unittest.TestCase):
    def setUp(self):
        self.root = repo()

    def _campaign(self) -> str:
        """A campaign branch beside `main`, held by nothing yet."""
        subprocess.run(("git", "-C", self.root, "branch", "campaign/test"),
                       capture_output=True, check=True)
        return "campaign/test"

    def _hold(self, branch: str) -> None:
        """Check `branch` out in a worktree, after the keeper already exists."""
        path = str(pathlib.Path(tempfile.mkdtemp()) / "held")
        subprocess.run(("git", "-C", self.root, "worktree", "add", "-q", path, branch),
                       capture_output=True, check=True)

    def _work(self) -> str:
        """A worktree with a change worth keeping, cut from the first commit."""
        path = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", self.root, "worktree", "add", "-q", "--detach",
                        path, "HEAD"), capture_output=True, check=True)
        (pathlib.Path(path) / "a.py").write_text("two\n")
        return path

    def test_the_main_line_is_never_the_destination(self):
        before = sha(self.root, "main")
        with self.assertRaises(RuntimeError):
            Keeper(self.root, "main").keep("T1", self._work(), "moved main")
        self.assertEqual(before, sha(self.root, "main"))

    def test_the_repositorys_own_default_branch_is_never_the_destination(self):
        subprocess.run(("git", "-C", self.root, "symbolic-ref",
                        "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk"),
                       capture_output=True, check=True)
        with self.assertRaises(RuntimeError):
            Keeper(self.root, "trunk").keep("T1", self._work(), "moved trunk")
        self.assertEqual([], subprocess.run(
            ("git", "-C", self.root, "branch", "--list", "trunk"),
            capture_output=True, text=True, check=True).stdout.split())

    def test_a_branch_a_worktree_has_checked_out_is_never_the_destination(self):
        side = str(pathlib.Path(tempfile.mkdtemp()) / "side")
        subprocess.run(("git", "-C", self.root, "worktree", "add", "-q", "-b", "side",
                        side), capture_output=True, check=True)
        before = sha(self.root, "side")
        with self.assertRaises(RuntimeError):
            Keeper(self.root, "side").keep("T1", self._work(), "moved side")
        self.assertEqual(before, sha(self.root, "side"))

    def test_a_symbolic_destination_is_never_the_main_line_by_another_name(self):
        subprocess.run(("git", "-C", self.root, "symbolic-ref",
                        "refs/heads/campaign/review", "refs/heads/main"),
                       capture_output=True, check=True)
        before = sha(self.root, "main")
        with self.assertRaises(RuntimeError):
            Keeper(self.root, "campaign/review").keep("T1", self._work(), "sideways")
        self.assertEqual(before, sha(self.root, "main"))

    def test_a_keep_refuses_a_destination_checked_out_after_the_keeper_was_made(self):
        keeper = Keeper(self.root, self._campaign())   # nothing held it then
        self._hold("campaign/test")
        before = sha(self.root, "campaign/test")
        with self.assertRaises(RuntimeError):
            keeper.keep("T1", self._work(), "moved under a live checkout")
        self.assertEqual(before, sha(self.root, "campaign/test"))

    def test_a_push_is_not_refused_by_a_worktree_holding_the_branch(self):
        # A push does not move the local campaign branch, so a checkout is no reason to refuse one —
        # and `push` never raises, or an unreachable remote would throw away
        # work already kept. The keep that would move the branch under that
        # checkout is refused at the ref motion; this only says the push is not.
        keeper = Keeper(self.root, self._campaign())
        self._hold("campaign/test")
        self.assertNotIn("checked out in a worktree", keeper.push())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
