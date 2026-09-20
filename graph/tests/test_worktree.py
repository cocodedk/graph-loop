"""One worktree per task, the file scope it may write, and the live-stack lock.

Written before `worktree.py`. Each case builds a throwaway git repository, so
nothing here touches the real one.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from worktree import LiveLock, Worktree, changed_outside

EXPECTED_TESTS = 17


def repo() -> str:
    root = tempfile.mkdtemp()
    run = lambda *args: subprocess.run(args, cwd=root, capture_output=True, check=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.email", "t@example.test")
    run("git", "config", "user.name", "test")
    (pathlib.Path(root) / "a.py").write_text("one\n")
    (pathlib.Path(root) / "b.py").write_text("two\n")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "first")
    return root


class WorktreeTest(unittest.TestCase):
    def test_a_task_gets_its_own_checkout_of_the_named_commit(self):
        root = repo()
        tree = Worktree(root, "T1").create()
        self.assertTrue((pathlib.Path(tree.path) / "a.py").exists())
        self.assertNotEqual(str(tree.path), root)
        tree.remove()

    def test_two_tasks_get_two_directories(self):
        root = repo()
        one, two = Worktree(root, "T1").create(), Worktree(root, "T2").create()
        self.assertNotEqual(one.path, two.path)
        one.remove(); two.remove()

    def test_a_worktree_is_kept_when_a_task_fails(self):
        root = repo()
        tree = Worktree(root, "T1").create()
        tree.keep("gate failed twice")
        self.assertTrue(pathlib.Path(tree.path).exists())
        self.assertIn("gate failed twice",
                      (pathlib.Path(tree.path) / "WHY-THIS-IS-KEPT.txt").read_text())

    def test_a_created_checkout_is_never_registered_as_a_linked_worktree(self):
        # A private clone, not `git worktree add`: nothing a builder does to
        # its refs could ever be a shared-worktree write if there is no shared
        # worktree to write to.
        root = repo()
        tree = Worktree(root, "T1").create()
        path = tree.path
        listed = subprocess.run(["git", "-C", root, "worktree", "list"],
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(1, len(listed.strip().splitlines()))   # the repo alone
        tree.remove()
        self.assertFalse(pathlib.Path(path).exists())

    def test_the_dirty_main_checkout_is_never_the_source(self):
        root = repo()
        (pathlib.Path(root) / "a.py").write_text("uncommitted mess\n")
        tree = Worktree(root, "T1").create()
        self.assertEqual("one\n", (pathlib.Path(tree.path) / "a.py").read_text())
        tree.remove()


    # `reuse` advancing a stale checkout to the loop's current base — the
    # ordinary case, the conflict, and a base that shares no line of history
    # with it — is `test_worktree_rebase`'s.


class ScopeTest(unittest.TestCase):
    def test_a_change_inside_the_list_is_allowed(self):
        root = repo()
        tree = Worktree(root, "T1").create()
        (pathlib.Path(tree.path) / "a.py").write_text("edited\n")
        self.assertEqual([], changed_outside(tree.path, ["a.py"]))
        tree.remove()

    def test_a_change_outside_the_list_is_named(self):
        root = repo()
        tree = Worktree(root, "T1").create()
        (pathlib.Path(tree.path) / "a.py").write_text("edited\n")
        (pathlib.Path(tree.path) / "b.py").write_text("also edited\n")
        self.assertEqual(["b.py"], changed_outside(tree.path, ["a.py"]))
        tree.remove()

    def test_a_new_file_outside_the_list_is_named_too(self):
        root = repo()
        tree = Worktree(root, "T1").create()
        (pathlib.Path(tree.path) / "c.py").write_text("invented\n")
        self.assertEqual(["c.py"], changed_outside(tree.path, ["a.py"]))
        tree.remove()


class ArtefactTest(unittest.TestCase):
    def test_what_running_the_gate_leaves_behind_is_not_an_edit(self):
        root = repo()
        tree = Worktree(root, "T1").create()
        (pathlib.Path(tree.path) / "a.py").write_text("edited\n")
        (pathlib.Path(tree.path) / "__pycache__").mkdir()
        (pathlib.Path(tree.path) / "__pycache__" / "a.cpython-312.pyc").write_text("x")
        self.assertEqual([], changed_outside(tree.path, ["a.py"]))
        tree.remove()


class DiffTest(unittest.TestCase):
    def test_a_new_file_is_part_of_the_diff_a_reviewer_sees(self):
        root = repo()
        tree = Worktree(root, "T1").create()
        (pathlib.Path(tree.path) / "born.py").write_text("def new():\n    return 1\n")
        diff = tree.diff()
        self.assertIn("born.py", diff)
        self.assertIn("def new():", diff)
        tree.remove()


class LiveLockTest(unittest.TestCase):
    def test_only_one_task_at_a_time_may_touch_the_live_stack(self):
        folder = tempfile.mkdtemp()
        first = LiveLock(folder)
        self.assertTrue(first.take("T2"))
        second = LiveLock(folder)
        self.assertFalse(second.take("T3"))
        self.assertEqual("T2", second.holder())
        first.give_back()
        self.assertTrue(second.take("T3"))


class StaleLockTest(unittest.TestCase):
    def test_a_lock_left_by_a_dead_driver_is_free(self):
        import pathlib as _p
        folder = tempfile.mkdtemp()
        (_p.Path(folder) / "live-stack.lock").write_text("T2 999999")
        self.assertTrue(LiveLock(folder).take("T3"))

    def test_a_lock_held_by_a_living_driver_is_not_free(self):
        folder = tempfile.mkdtemp()
        self.assertTrue(LiveLock(folder).take("T2"))     # this process holds it
        self.assertFalse(LiveLock(folder).take("T3"))

    def test_the_lock_names_a_process_not_a_group(self):
        """The driver shares its group with the supervisor that restarts it, so
        a group that answers proves nothing about the driver."""
        import os
        import pathlib as _p
        folder = tempfile.mkdtemp()
        LiveLock(folder).take("T2")
        parts = (_p.Path(folder) / "live-stack.lock").read_text("utf-8").split()
        self.assertEqual(["T2", str(os.getpid())], parts[:2])
        self.assertEqual(3, len(parts))                  # and the start it began at

    def test_a_lock_whose_pid_was_reused_is_free(self):
        import os
        import pathlib as _p
        folder = tempfile.mkdtemp()
        (_p.Path(folder) / "live-stack.lock").write_text(
            f"T2 {os.getpid()} some-other-boot:1")       # this pid, a different process
        self.assertTrue(LiveLock(folder).take("T3"))

    def test_a_lock_that_cannot_be_read_is_held_never_free(self):
        import pathlib as _p
        folder = tempfile.mkdtemp()
        (_p.Path(folder) / "live-stack.lock").write_text("half-a-line")
        self.assertFalse(LiveLock(folder).take("T3"))



class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
