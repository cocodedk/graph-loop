"""A checkout whose HEAD left the base is still paid work: saved before it goes.

Two sites deleted such a tree outright — the builder's own move (`worktree_refs.
discard`) and a gate that moved HEAD (`loop_judge_retry.gate_left_its_lane`) —
so an hour of edits went with the directory (astra's round-4 finding 6). Both
now write the tree down against the RECORDED base first and point the card at
the diff. Against the base, not HEAD: HEAD is exactly what cannot be trusted
here, and the first case below has the edits INSIDE the moved HEAD, where a
diff against HEAD reads as nothing at all.

How HEAD got there is what the driver cannot know (`HeadMoved`); the hook
refuses a commit and lets a switch to an existing branch through, and either
way the tree can no longer be read as the base plus edits.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_loop import Fakes, loop_for, task
from worktree import HeadMoved, Worktree

EXPECTED_TESTS = 3


def builder_that_commits(prompt, *, cwd, **kwargs):
    """Edits a.py and puts the edit inside a commit of its own, so HEAD is off
    the base and `git diff HEAD` in that tree is empty."""
    (pathlib.Path(cwd) / "a.py").write_text("two\n")
    for args in (("add", "-A"),
                 ("-c", "user.email=b@example.test", "-c", "user.name=builder",
                  "commit", "-qm", "off the base")):
        subprocess.run(("git", "-C", cwd, "-c", "core.hooksPath=", *args),
                       capture_output=True, check=True)
    return Fakes().build[0]


def raises_on(number: int):
    """A stand-in for `Worktree.on_base` that answers until the `number`th ask.

    The order on a full round is red-first's gate, the post-build check, then
    the judge's own gate run — so the gate path is only reached by counting."""
    asked = []

    def on_base(self):
        asked.append(1)
        if len(asked) == number:
            raise HeadMoved("f00d")

    return on_base


def saved_diffs(book) -> list[str]:
    return [pathlib.Path(one).read_text("utf-8", errors="replace")
            for one in (book.task("T1").get("lost_edits") or [])]


class MovedHeadSalvageTest(unittest.TestCase):
    def test_a_builders_own_move_leaves_the_edits_written_down(self):
        fakes = Fakes()
        fakes.builder = builder_that_commits
        loop, book, _ = loop_for(task(triage="work"), fakes)
        loop.run_task(book.task("T1"))

        kept = saved_diffs(book)
        self.assertEqual(1, len(kept), book.task("T1"))
        self.assertIn("two", kept[0])
        self.assertIsNone(book.task("T1").get("rebuild_from"))   # a fresh tree next round

    def test_a_save_that_fails_keeps_the_tree_instead_of_deleting_it(self):
        """What authorises the deletion is the save succeeding, never the fault
        that ordered it. A full disk is how this campaign met that."""
        fakes = Fakes()
        fakes.builder = builder_that_commits
        loop, book, space = loop_for(task(triage="work"), fakes)
        wrote = space.artifact

        def no_room(task_id, name, text):
            if name == "lost-edits":
                raise OSError("no space left on device")
            return wrote(task_id, name, text)

        with mock.patch.object(space, "artifact", no_room):
            loop.run_task(book.task("T1"))

        cut = [row["path"] for row in space.events() if row.get("kind") == "worktree"]
        self.assertTrue(pathlib.Path(cut[-1]).is_dir(), cut)
        row = book.task("T1")
        self.assertIn("could not be saved", row["edits_unsaved"])
        self.assertNotIn("lost_edits", row)
        self.assertIsNone(row.get("rebuild_from"))   # kept, but never reused

    def test_a_gate_that_moved_head_leaves_the_edits_written_down(self):
        loop, book, _ = loop_for(task(triage="work"), Fakes())
        with mock.patch.object(Worktree, "on_base", raises_on(3)):
            loop.run_task(book.task("T1"))

        kept = saved_diffs(book)
        self.assertEqual(1, len(kept), book.task("T1"))
        self.assertIn("two", kept[0])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
