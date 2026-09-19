"""The sweep removes only the worktrees of settled cards: an open card's tree —
referenced or not — stays, and so does a tree whose card is unknown but open;
a done card's tree and its empty parent go."""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from sweep_trees import sweep

EXPECTED_TESTS = 3


class SweepTest(unittest.TestCase):
    def test_settled_trees_go_and_open_trees_stay(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        def tree(parent, tid):
            p = tmp / parent / f"task-{tid}"
            p.mkdir(parents=True)
            (p / "work.txt").write_text("x")
            return str(p)
        done_tree = tree("drive-aaa", "T1")
        open_tree = tree("drive-bbb", "T2")
        resumed = tree("drive-ccc", "T3")
        unknown = tree("drive-ddd", "T-nobody")               # not in this backlog at all
        namesake = tree("drive-eee", "T1")                     # a done card's NAME, not its path
        (tmp / "drive-fff").mkdir()                            # a build's parent, tree not yet made
        tasks = [{"id": "T1", "status": "done", "worktree": done_tree},
                 {"id": "T2", "status": "rejected"},
                 {"id": "T3", "status": "todo", "rebuild_from": resumed}]
        gone = sweep(tasks, tmp)
        self.assertEqual([done_tree], gone)
        self.assertFalse(pathlib.Path(done_tree).exists())
        self.assertFalse((tmp / "drive-aaa").exists())          # empty parent gone too
        for kept in (open_tree, resumed, unknown, namesake, str(tmp / "drive-fff")):
            self.assertTrue(pathlib.Path(kept).exists(), kept)

    def test_a_tree_that_will_not_go_is_not_counted(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        p = tmp / "drive-yyy" / "task-T8"; p.mkdir(parents=True)
        (p / "held").mkdir(); (p / "held" / "f").write_text("x")
        (p / "held").chmod(0o500)                              # its child cannot be unlinked
        self.addCleanup((p / "held").chmod, 0o700)
        with contextlib.redirect_stderr(io.StringIO()) as said:
            gone = sweep([{"id": "T8", "status": "done", "worktree": str(p)}], tmp)
        self.assertEqual([], gone)
        self.assertTrue(p.exists())
        self.assertIn("stays", said.getvalue())

    def test_dry_run_removes_nothing(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        p = tmp / "drive-zzz" / "task-T9"; p.mkdir(parents=True)
        gone = sweep([{"id": "T9", "status": "dropped", "worktree": str(p)}], tmp, dry=True)
        self.assertEqual([str(p)], gone)
        self.assertTrue(p.exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
