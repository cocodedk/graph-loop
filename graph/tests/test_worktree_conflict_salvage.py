"""A kept tree whose edits conflict with what landed on the base is paid work:
before the tree goes, its edits are written down as a diff, and the fresh
round is told where they are (astra's review of 2026-09-08, finding 1)."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from providers import Outcome
from test_loop import Fakes, loop_for, task
from worktree import HeadMoved, Worktree

EXPECTED_TESTS = 6


class ConflictSalvageTest(unittest.TestCase):
    def test_a_reuse_conflict_saves_the_edits_and_tells_the_next_round(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)
        (pathlib.Path(first.worktree) / "a.py").write_text("paid edit\n")
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        rejections=["1. wrong line"], refused_why=None)

        def conflicts(self, path):
            self.path = path
            raise HeadMoved("deadbeef",
                            why="the kept edits conflict with what landed on the base since")

        real_reuse = Worktree.reuse
        Worktree.reuse = conflicts
        try:
            again = loop.run_task(book.task("T1"))
        finally:
            Worktree.reuse = real_reuse

        self.assertEqual("done", again.state, again.why)
        lost = [r for r in space.events() if r.get("task") == "T1" and r["kind"] == "rebuild_lost"]
        saved = lost[-1].get("saved", "")
        self.assertTrue(saved, "the paid edits were not written down")
        self.assertIn("paid edit", pathlib.Path(saved).read_text())
        self.assertIn(saved, fakes.prompts[-1])                 # the next round is told where

    def test_the_pointer_stands_until_a_builder_has_read_it(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok")] * 4)
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        rejections=["1. wrong line"], refused_why=None)
        real_reuse = Worktree.reuse

        def conflicts(self, path):
            self.path = path
            raise HeadMoved("deadbeef", why="the kept edits conflict with what landed on the base since")

        Worktree.reuse = conflicts
        fakes.build = [Outcome("limit", text="usage limit reached")]   # this round's builder is refused
        fakes.edit = None
        try:
            waited = loop.run_task(book.task("T1"))
        finally:
            Worktree.reuse = real_reuse
        self.assertEqual("waiting", waited.state, waited.why)
        saved = book.task("T1")["lost_edits"][0]
        fakes.build = [Outcome("ok", text="DONE")]
        fakes.edit = "two\n"
        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state, again.why)
        self.assertIn(saved, fakes.prompts[-1])                 # the retry is still told where
        self.assertFalse(book.task("T1").get("lost_edits"))     # and after it read, the pointer goes


class PointerInPlaceTest(unittest.TestCase):
    def test_a_round_continued_in_place_is_still_told_where_the_edits_are(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok")] * 4)
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        rejections=["1. wrong line"], refused_why=None)
        real_reuse = Worktree.reuse

        def conflicts(self, path):
            self.path = path
            raise HeadMoved("deadbeef", why="the kept edits conflict with what landed on the base since")

        Worktree.reuse = conflicts
        fakes.build = [Outcome("crash", text="")]               # paid, and went wrong: continues in place
        try:
            crashed = loop.run_task(book.task("T1"))
        finally:
            Worktree.reuse = real_reuse
        self.assertEqual("harness", crashed.state, crashed.why)
        saved = book.task("T1")["lost_edits"][0]
        fakes.build = [Outcome("ok", text="DONE")]
        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state, again.why)
        self.assertIn("do not start over", fakes.prompts[-1])
        self.assertIn(saved, fakes.prompts[-1])
        self.assertFalse(book.task("T1").get("lost_edits"))


class PointerBeforeRemovalTest(unittest.TestCase):
    def test_a_death_right_after_the_salvage_still_leaves_the_pointer(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok")] * 4)
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        rejections=["1. wrong line"], refused_why=None)
        real_reuse, real_create = Worktree.reuse, Worktree.create

        def conflicts(self, path):
            self.path = path
            raise HeadMoved("deadbeef", why="the kept edits conflict with what landed on the base since")

        def dies(self, parent=None):
            raise OSError(28, "No space left on device")

        Worktree.reuse, Worktree.create = conflicts, dies
        try:
            with self.assertRaises(OSError):
                loop.run_task(book.task("T1"))
        finally:
            Worktree.reuse, Worktree.create = real_reuse, real_create
        saved = (book.task("T1").get("lost_edits") or [""])[0]
        self.assertTrue(saved, "the pointer died with the tree")
        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state, again.why)
        self.assertIn(saved, fakes.prompts[-1])


class TwoConflictsTest(unittest.TestCase):
    def test_a_second_conflict_adds_a_pointer_and_a_blocked_answer_keeps_them(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok")] * 6)
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        rejections=["1. wrong line"], refused_why=None)
        real_reuse = Worktree.reuse

        def conflicts(self, path):
            self.path = path
            raise HeadMoved("deadbeef", why="the kept edits conflict with what landed on the base since")

        fakes.build = [Outcome("ok", text='{"result": "BLOCKED", "why": "the diff could not be read"}')]
        for _round in range(2):                                # conflict, blocked; conflict, blocked
            Worktree.reuse = conflicts
            try:
                out = loop.run_task(book.task("T1"))
            finally:
                Worktree.reuse = real_reuse
            self.assertEqual("blocked", out.state, out.why)
            book.set_status("T1", "todo", rebuild_from=out.worktree, refused_why=None)
        pointers = book.task("T1")["lost_edits"]
        self.assertEqual(2, len(pointers))                    # neither replaced the other
        for saved in pointers:
            self.assertIn(saved, fakes.prompts[-1])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
