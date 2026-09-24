"""The driver closes every lane, and retries use new checkouts."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lane_closing
from keep import Keeper
from lanes import run_lanes
from loop_tree import for_this_round
from loop_types import TaskOutcome
from test_loop import Fakes, loop_for, task
from worktree import Worktree


class ClosingTest(unittest.TestCase):
    def test_every_ending_removes_only_the_turns_checkout(self):
        for state in ("done", "dropped", "refused", "quarantined", "crashed"):
            with self.subTest(state=state):
                loop, book, space = loop_for(task(), Fakes())
                unrelated = Worktree(loop.repo, "other").create()
                self.addCleanup(unrelated.remove)
                paths = []

                def run(card, loop=loop, paths=paths, book=book, state=state):
                    tree, _ = for_this_round(loop, card)
                    paths.append(pathlib.Path(tree.path))
                    tree.keep("unfinished")
                    book.note(card["id"], rebuild_from=tree.path, session="old")
                    if state == "crashed":
                        raise RuntimeError("lane crashed")
                    return TaskOutcome(state, "")

                loop.run_task = run
                with patch("lane_closing.capacity", return_value=""):
                    run_lanes(loop, book, space, book.tasks())
                self.assertFalse(paths[0].exists())
                self.assertFalse(paths[0].parent.exists())
                self.assertTrue(pathlib.Path(unrelated.path).exists())
                self.assertFalse(book.task("T1").get("rebuild_from"))
                self.assertEqual("", book.task("T1")["session"])
                self.assertEqual({}, space.running())

    def test_a_retry_keeps_findings_and_budget_but_not_edits_or_session(self):
        loop, book, space = loop_for(task(), Fakes())
        paths = []

        def run(card):
            tree, reused = for_this_round(loop, card)
            self.assertFalse(reused)
            paths.append(tree.path)
            self.assertEqual("one\n", (pathlib.Path(tree.path) / "a.py").read_text())
            if len(paths) == 2:
                self.assertEqual(1, card["rebuild_round"])
                self.assertEqual(["repair it"], card["rejections"])
                self.assertFalse(card.get("session"))
            (pathlib.Path(tree.path) / "a.py").write_text("unfinished\n")
            book.note(card["id"], rebuild_from=tree.path, rebuild_round=1,
                      rejections=["repair it"], session="old", finished={"phase": "gate"})
            return TaskOutcome("waiting", "")

        loop.run_task = run
        with patch("lane_closing.capacity", return_value=""):
            run_lanes(loop, book, space, book.tasks())
            run_lanes(loop, book, space, book.tasks())
        self.assertNotEqual(*paths)
        self.assertFalse(book.task("T1").get("finished"))

    def test_kept_work_survives_removal_of_private_branches_and_records(self):
        loop, book, space = loop_for(task(), Fakes())
        keeper = Keeper(loop.repo, "campaign")
        paths = []

        def run(card):
            tree, _ = for_this_round(loop, card)
            paths.append(pathlib.Path(tree.path))
            subprocess.run(["git", "-C", tree.path, "-c", "core.hooksPath=",
                            "branch", "private"], check=True, capture_output=True)
            (paths[-1] / "a.py").write_text("two\n")
            keeper.keep(card["id"], tree.path, "accepted", files=["a.py"])
            return TaskOutcome("done", "")

        loop.run_task = run
        with patch("lane_closing.capacity", return_value=""):
            run_lanes(loop, book, space, book.tasks())
        self.assertFalse(paths[0].exists())
        kept = subprocess.check_output(["git", "-C", loop.repo, "show", "campaign:a.py"], text=True)
        self.assertEqual("two\n", kept)
        refs = subprocess.check_output(["git", "-C", loop.repo, "branch", "--list"], text=True)
        self.assertNotIn("private", refs)
        records = subprocess.check_output(["git", "-C", loop.repo, "worktree", "list"], text=True)
        self.assertNotIn(str(paths[0]), records)

    def test_creation_failure_is_still_closed(self):
        loop, book, space = loop_for(task(), Fakes())
        paths = []

        def broken(tree):
            paths.append(pathlib.Path(tree.path))
            raise OSError("provision failed")

        with (patch("lane_closing.capacity", return_value=""),
              patch.object(Worktree, "_hooked", broken)):
            run_lanes(loop, book, space, book.tasks())
        self.assertFalse(paths[0].exists())
        self.assertFalse(paths[0].parent.exists())

    def test_failed_removal_is_reported_and_does_not_skip_other_lanes(self):
        loop, book, space = loop_for(task(), Fakes())
        first = Worktree(loop.repo, "first").create()
        second = Worktree(loop.repo, "second").create()
        self.addCleanup(first.remove)
        second_path = pathlib.Path(second.path)
        with patch.object(first, "remove", side_effect=OSError("disk refused")):
            failures = lane_closing.close({"first": [first], "second": [second]},
                                          {"first": [], "second": []}, book, space)
        self.assertEqual(1, len(failures))
        self.assertFalse(second_path.exists())

    def test_low_capacity_waits_without_claiming_or_changing_the_card(self):
        loop, book, space = loop_for(task(), Fakes())
        before = book.task("T1")
        with (patch("lane_closing.capacity", return_value="waiting for free disk"),
              patch.object(loop, "run_task") as run):
            self.assertEqual((0, True), run_lanes(loop, book, space, book.tasks()))
        run.assert_not_called()
        self.assertEqual(before, book.task("T1"))
        self.assertEqual({}, space.running())

    def test_capacity_requires_memory_and_both_filesystems(self):
        with patch("lane_closing.meminfo", return_value={}):
            self.assertIn("memory", lane_closing.capacity("."))
        with (patch("lane_closing.meminfo", return_value={"MemAvailable": 1024 ** 3}),
              patch("lane_closing.shutil.disk_usage") as disk):
            disk.return_value.free = lane_closing.DISK_FLOOR_BYTES
            self.assertEqual("", lane_closing.capacity("."))
            self.assertEqual(2, disk.call_count)
            disk.return_value.free = 0
            self.assertIn("disk", lane_closing.capacity("."))


if __name__ == "__main__":
    unittest.main()
