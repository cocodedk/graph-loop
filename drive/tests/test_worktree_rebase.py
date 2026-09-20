"""The gap `Worktree.reuse` closes: a kept tree's own HEAD is the base it was
cut from, and the loop's own base can have moved on since — another card may
have landed on it. `reuse` advances the checkout to the current base when it
can (a straight-line move; git carries the kept, uncommitted edits across
when they do not conflict), raises `HeadMoved` when it cannot (a conflict),
and leaves the tree alone when there is nothing to advance to. The run_task
case proves the caller's own side: a conflict costs no rebuild round and
lands on a fresh tree, the same path a lost worktree already takes.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task
from test_worktree import repo
from test_worktree_refs import git
from worktree import HeadMoved, Worktree

EXPECTED_TESTS = 7


class AdvanceTest(unittest.TestCase):
    def test_a_stale_kept_tree_is_advanced_to_the_current_base(self):
        root = repo()
        first = Worktree(root, "T1", "HEAD").create()
        old_head = git(first.path, "rev-parse", "HEAD")
        (pathlib.Path(first.path) / "a.py").write_text("kept edit\n")
        (pathlib.Path(first.path) / "new_module.py").write_text("def new(): pass\n")
        # what `tree.diff()` already ran before this tree was ever kept
        subprocess.run(["git", "-C", first.path, "add", "-N", "--", "."], check=True)
        (pathlib.Path(root) / "b.py").write_text("landed\n")
        subprocess.run(["git", "-C", root, "commit", "-aqm", "a sibling lands"], check=True)
        new_base = git(root, "rev-parse", "HEAD")

        again = Worktree(root, "T1", new_base).reuse(first.path)

        self.assertEqual(new_base, again.commit)
        self.assertEqual((old_head, new_base), again.rebased)
        self.assertEqual(new_base, git(again.path, "rev-parse", "HEAD"))
        self.assertEqual("landed\n", (pathlib.Path(again.path) / "b.py").read_text())
        self.assertEqual("kept edit\n", (pathlib.Path(again.path) / "a.py").read_text())
        self.assertEqual("def new(): pass\n",
                         (pathlib.Path(again.path) / "new_module.py").read_text())

    def test_a_conflicting_kept_edit_raises_and_leaves_the_tree_untouched(self):
        root = repo()
        first = Worktree(root, "T1", "HEAD").create()
        old_head = git(first.path, "rev-parse", "HEAD")
        (pathlib.Path(first.path) / "a.py").write_text("kept edit\n")
        (pathlib.Path(root) / "a.py").write_text("landed on the same file\n")
        subprocess.run(["git", "-C", root, "commit", "-aqm", "a sibling lands on a.py too"],
                       check=True)
        new_base = git(root, "rev-parse", "HEAD")

        with self.assertRaises(HeadMoved) as caught:
            Worktree(root, "T1", new_base).reuse(first.path)

        self.assertIn("the kept edits conflict with what landed", caught.exception.said)
        self.assertEqual(old_head, git(first.path, "rev-parse", "HEAD"))
        self.assertEqual("kept edit\n", (pathlib.Path(first.path) / "a.py").read_text())

    def test_an_unmoved_base_is_left_alone(self):
        root = repo()
        first = Worktree(root, "T1", "HEAD").create()
        old_head = git(first.path, "rev-parse", "HEAD")

        again = Worktree(root, "T1", "HEAD").reuse(first.path)

        self.assertIsNone(again.rebased)
        self.assertEqual(old_head, again.commit)

    def test_a_diverged_base_raises_instead_of_reusing_a_stale_tree(self):
        # The tree's own commit A and the branch's commit B share a parent
        # but neither is an ancestor of the other — a fork, not an advance.
        root = repo()
        parent = git(root, "rev-parse", "HEAD")
        (pathlib.Path(root) / "a.py").write_text("commit A, the tree's own base\n")
        subprocess.run(["git", "-C", root, "commit", "-aqm", "A"], check=True)
        first = Worktree(root, "T1", "HEAD").create()
        old_head = git(first.path, "rev-parse", "HEAD")

        subprocess.run(["git", "-C", root, "checkout", "-q", parent], check=True)
        (pathlib.Path(root) / "a.py").write_text("commit B, a different line\n")
        subprocess.run(["git", "-C", root, "commit", "-aqm", "B"], check=True)
        diverged = git(root, "rev-parse", "HEAD")

        with self.assertRaises(HeadMoved) as caught:
            Worktree(root, "T1", diverged).reuse(first.path)

        self.assertIn("not on the branch any more", caught.exception.said)
        self.assertEqual(old_head, git(first.path, "rev-parse", "HEAD"))

    def test_a_git_failure_during_checkout_raises_plainly_and_leaves_everything(self):
        # A stale index.lock (a crashed git process, a disk hiccup) says
        # nothing about the tree's own edits: not a conflict, not a
        # divergence, so it must not be read as either — a paid-for tree is
        # left standing for a person, not discarded on a guess.
        root = repo()
        first = Worktree(root, "T1", "HEAD").create()
        old_head = git(first.path, "rev-parse", "HEAD")
        (pathlib.Path(first.path) / "a.py").write_text("kept edit\n")
        (pathlib.Path(root) / "b.py").write_text("landed\n")
        subprocess.run(["git", "-C", root, "commit", "-aqm", "a sibling lands"], check=True)
        new_base = git(root, "rev-parse", "HEAD")
        (pathlib.Path(first.path) / ".git" / "index.lock").touch()

        with self.assertRaises(RuntimeError) as caught:
            Worktree(root, "T1", new_base).reuse(first.path)

        self.assertNotIsInstance(caught.exception, HeadMoved)
        self.assertEqual(old_head, git(first.path, "rev-parse", "HEAD"))
        self.assertEqual("kept edit\n", (pathlib.Path(first.path) / "a.py").read_text())


class RunTaskConflictTest(unittest.TestCase):
    def test_a_reuse_conflict_costs_no_round_and_lands_on_a_fresh_tree(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        rejections=["1. wrong line"], refused_why=None)

        def conflicts(self, path):
            self.path = path   # the real `reuse` also sets this before it can raise
            raise HeadMoved("deadbeef",
                            why="the kept edits conflict with what landed on the base since")

        real_reuse = Worktree.reuse
        Worktree.reuse = conflicts
        try:
            again = loop.run_task(book.task("T1"))
        finally:
            Worktree.reuse = real_reuse

        self.assertEqual("done", again.state, again.why)
        self.assertNotEqual(first.worktree, again.worktree)
        self.assertFalse(pathlib.Path(first.worktree).exists())
        self.assertEqual(1, book.task("T1")["rebuild_round"])   # no round charged
        lost = [r for r in space.events() if r.get("task") == "T1" and r["kind"] == "rebuild_lost"]
        self.assertTrue(lost)
        self.assertIn("the kept edits conflict with what landed", lost[-1].get("why", ""))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
