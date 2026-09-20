"""A campaign branch is looked up as a branch, never as whatever answers first.

`git rev-parse campaign/fresh` prefers a TAG of that name over the branch, so a
tag left in the repository silently sent the keeper and the slicer
to another commit — the keeper would start the next task from it, and the slicer
would plan against it (an independent review). Every campaign-branch lookup asks for
`refs/heads/<name>` now (`keep_branch.qualified`).
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

GRAPH = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRAPH / "lib"))
import slice_turn
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper
from keep_branch import campaign_branch, tip_of
from test_keep import repo, sha
from test_turn_slice import tree_with
from workspace import Workspace

EXPECTED_TESTS = 6
BRANCH = "campaign/fresh"
WALL = {"id": "T1", "status": "needs_slice", "goal": "g", "files": ["app.py"],
        "triage": "work", "refused_why": "the gate said why"}


def branch_and_tag() -> tuple[str, str, str]:
    """A repository where the branch and a tag of the same name differ."""
    root = repo()
    on_branch = sha(root)
    subprocess.run(("git", "-C", root, "branch", BRANCH, on_branch),
                   capture_output=True, check=True)
    (pathlib.Path(root) / "a.py").write_text("later\n")
    subprocess.run(("git", "-C", root, "commit", "-aqm", "later"),
                   capture_output=True, check=True)
    subprocess.run(("git", "-C", root, "tag", BRANCH, "HEAD"),
                   capture_output=True, check=True)
    return root, on_branch, sha(root)


def tag_only() -> tuple[str, str]:
    """A repository with NO campaign branch and a tag named like its full ref.

    `git rev-parse refs/heads/campaign/fresh` falls back to `refs/tags/` when
    the branch is absent, so asking for the full ref was still not asking for a
    branch (an independent review).
    """
    root = repo()
    tagged = sha(root)
    subprocess.run(("git", "-C", root, "tag", f"refs/heads/{BRANCH}", tagged),
                   capture_output=True, check=True)
    (pathlib.Path(root) / "a.py").write_text("later\n")     # so HEAD is not the tag
    subprocess.run(("git", "-C", root, "commit", "-aqm", "later"),
                   capture_output=True, check=True)
    return root, tagged


class MissingBranchTest(unittest.TestCase):
    def test_a_branch_that_is_not_there_is_not_there(self):
        root, tagged = tag_only()
        keeper = Keeper(root, BRANCH)
        self.assertFalse(keeper.exists(), "a tag answered for a branch nobody made")
        self.assertNotEqual(tagged, keeper.tip())      # the base, not the tag

    def test_a_tag_is_no_tip_to_bind_to(self):
        root, _tagged = tag_only()
        space = Workspace(tempfile.mkdtemp()).init(goal="t", backlog="x", branch=BRANCH)
        with mock.patch.dict(os.environ, {"GRAPH_REPO": root}):
            self.assertEqual("", tip_of(space))

    def test_init_still_makes_the_branch(self):
        root, _tagged = tag_only()
        made = campaign_branch(root, BRANCH)
        self.assertEqual(f"refs/heads/{BRANCH}", made)
        heads = subprocess.run(("git", "-C", root, "for-each-ref", "--format=%(refname)",
                                "refs/heads"), capture_output=True, text=True,
                               check=True).stdout.split()
        self.assertIn(f"refs/heads/{BRANCH}", heads)


class KeeperTipTest(unittest.TestCase):
    def test_the_next_task_starts_from_the_branch_not_the_tag(self):
        root, on_branch, tagged = branch_and_tag()
        self.assertNotEqual(on_branch, tagged)
        self.assertEqual(on_branch, Keeper(root, BRANCH).tip())


class DeciderTipTest(unittest.TestCase):
    def test_the_decision_is_bound_to_the_branchs_own_tip(self):
        root, on_branch, _tagged = branch_and_tag()
        space = Workspace(tempfile.mkdtemp()).init(goal="t", backlog="x", branch=BRANCH)
        with mock.patch.dict(os.environ, {"GRAPH_REPO": root}):
            self.assertEqual(on_branch, tip_of(space))


class SlicerCheckoutTest(unittest.TestCase):
    def test_the_slicer_resolves_the_branch_as_a_branch(self):
        """The tip it asks for becomes the clean checkout it plans against."""
        root, _on_branch, _tagged = branch_and_tag()
        space = Workspace(tempfile.mkdtemp()).init(goal="t", backlog="x", branch=BRANCH)
        space.event("sources_declared", sources=["simulation/spec"])
        asked: list = []

        def plumbing(argv, **_kw):
            if argv[0] != "git":
                raise AssertionError(f"the slicer must go through runner.run: {argv[:2]}")
            asked.append(argv)
            return mock.Mock(returncode=1, stdout="", stderr="stubbed")

        with mock.patch.dict(os.environ, {"GRAPH_REPO": root}), \
                mock.patch("subprocess.run", side_effect=plumbing), \
                mock.patch("runner.run", side_effect=AssertionError("nothing is paid here")), \
                contextlib.suppress(AssertionError):
            slice_turn.slice_pending(tree_with(WALL), space)
        asked_for = [argv for argv in asked if "show-ref" in argv]
        self.assertTrue(asked_for, f"the branch was never resolved: {asked}")
        self.assertEqual(("--verify", "--hash", f"refs/heads/{BRANCH}"),
                         tuple(asked_for[0][-3:]))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
