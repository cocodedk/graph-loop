"""A record is on the platter before the step that depends on it runs.

Power loss keeps what the disk already holds. A deletion or a live action that
outruns its own recovery record leaves the loop with the destruction and none
of the proof: the salvage diff and the card pointing at it before the tree is
removed, the pending-keep note before the ref moves, the card that says a live
call is open before the call (astra's review of 2026-09-08, round 2, finding 4).

The fake `os.fsync` records what reached the platter, in order, beside the step
that must come after it. It records the CONTENT of each file too, because the
same card is written many times in a turn and an earlier write of it answers
nothing about this one (an independent review).
"""

from __future__ import annotations

import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import keep
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from test_keep import repo
from test_loop import Fakes, loop_for, task
from workspace import Workspace
from worktree import HeadMoved
from worktree_refs import reuse_or_salvage

EXPECTED_TESTS = 4


def watching(order: list):
    """Every fsync as (what, content): a file under the name its readers use,
    a folder under its own name and a trailing slash. Linux reads the path back
    from the descriptor."""
    real = os.fsync

    def fake(fd: int) -> None:
        real(fd)
        put = pathlib.Path(os.readlink(f"/proc/self/fd/{fd}"))
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            order.append((f"{put.name}/", ""))
            return
        order.append((put.name.lstrip(".").removesuffix(".tmp"),
                      put.read_text("utf-8", "replace")))

    return mock.patch("os.fsync", fake)


def at(case, order: list, what: str, holds: str = "") -> int:
    """Where `what` reached the platter — the first one saying `holds`."""
    for index, (name, text) in enumerate(order):
        if name == what and holds in text:
            return index
    raise case.failureException(
        f"{what} {holds}".strip() + f" never reached the platter: {[name for name, _ in order]}")


def before(case, first: str, second: str, order: list, holds: str = "") -> None:
    case.assertLess(at(case, order, first, holds), at(case, order, second),
                    f"{first} was written after {second}: {[name for name, _ in order]}")


class SalvageTest(unittest.TestCase):
    def test_the_diff_and_the_card_are_on_the_platter_before_the_tree_goes(self):
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "T1").mkdir()
        (root / "T1" / "molecule.md").write_text(
            cardfile.dump({"goal": "make a.py say two", "status": "todo"}), "utf-8")
        loop = types.SimpleNamespace(
            space=Workspace(pathlib.Path(tempfile.mkdtemp()) / "campaign").init(
                goal="pilot", backlog=str(root)),
            backlog=Backlog(root))
        order: list = []

        class Tree:
            def reuse(self, previous):
                raise HeadMoved("deadbeef", why="the kept edits conflict with what landed")

            def diff(self, binary=False):
                return "diff --git a/a.py b/a.py\n+paid edit\n"

            def remove(self):
                order.append(("remove", ""))

        with watching(order):
            in_place, _why, saved = reuse_or_salvage(loop, "T1", Tree(), "/gone")
        self.assertFalse(in_place)
        self.assertIn("paid edit", pathlib.Path(saved).read_text("utf-8"))
        before(self, "001-lost-edits.txt", "remove", order)   # the diff itself
        before(self, "molecule.md", "remove", order)        # and the card that points at it
        # The folders it was written into are new, and a folder nothing named on
        # the platter takes the file with it: `calls` and `calls/T1` are named by
        # the campaign root and by `calls`, and both entries go down first.
        before(self, "campaign/", "remove", order)
        before(self, "calls/", "remove", order)


class PendingNoteTest(unittest.TestCase):
    def test_the_note_is_on_the_platter_before_the_ref_moves(self):
        root = repo()
        keeper = keep.Keeper(root, "campaign/test")
        tree = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", tree,
                        keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(tree) / "a.py").write_text("two\n")
        order: list = []
        real = keep.subprocess.run

        def run(args, **kw):
            if "update-ref" in args:
                order.append(("update-ref", ""))
            return real(args, **kw)

        with watching(order), mock.patch.object(keep.subprocess, "run", run):
            commit = keeper.keep("T1", tree, "made it two")
        before(self, "keep-pending-campaign%2Ftest-T1", "update-ref", order, holds=commit)
        before(self, ".git/", "update-ref", order)   # and the folder: the name itself can be lost


class LiveCallOpenTest(unittest.TestCase):
    def test_the_card_is_on_the_platter_before_the_live_call(self):
        """The write that says the call is open, not merely some earlier write
        of the same card: the card is named by its content, and the folder
        entry that follows that write is named too."""
        loop, book, _ = loop_for(
            task(gate_has_side_effects=True, gate="true", helper_verbs=["journal"]), Fakes())
        order: list = []

        def dies(prompt, **kw):
            order.append(("live call", ""))
            raise RuntimeError("the driver died in the call")

        loop.build = dies
        with watching(order), self.assertRaises(RuntimeError):
            loop.run_task(book.task("T1"))
        self.assertEqual("live_call_open", book.task("T1")["status"])
        wrote = at(self, order, "backlog.yaml", holds="live_call_open")
        call = at(self, order, "live call")
        self.assertLess(wrote, call, "the call ran before the card said it was open")
        self.assertTrue([index for index, (name, _) in enumerate(order)
                         if name.endswith("/") and wrote < index < call],
                        "no folder entry followed that write before the call")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
