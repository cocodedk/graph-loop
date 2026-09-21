"""Restart at unfinished branch frontiers without reopening accepted cards."""

import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from campaigns import CODE, campaign
from keep_failure import CombinedGateFailed
from loop import Loop
from loop_judge_gates import _send_to_its_owner
from turn_plan import taking_now

EXPECTED_TESTS = 4


class FinishedCardsTest(unittest.TestCase):
    def test_a_finished_card_never_opens_a_worktree_or_calls_an_agent(self):
        done = {**CODE, "id": "done", "status": "done", "commit": "accepted",
                "rebuild_from": "old-worktree", "session": "old-session"}
        book, space = campaign([done])
        loop = Loop(repo=".", backlog=book, space=space,
                    build=lambda *a, **k: self.fail("a finished card reached a builder"),
                    review=lambda *a, **k: self.fail("a finished card reached a reviewer"))
        with patch("loop.for_this_round", side_effect=AssertionError("a finished card opened a worktree")):
            loop.run_task(book.task("done"))
        self.assertEqual(done, book.task("done"))

    def test_an_old_gate_failure_never_reopens_its_finished_owner(self):
        owner = {**CODE, "id": "owner", "status": "done", "commit": "accepted",
                 "gate": "false", "gate_rounds": 2, "rebuild_round": 2}
        pending = {**CODE, "id": "pending", "status": "todo"}
        book, space = campaign([owner, pending])
        loop = types.SimpleNamespace(backlog=book, space=space)
        tree = types.SimpleNamespace(path="kept-worktree", keep=lambda why: None)
        _send_to_its_owner(loop, pending, tree, "owner", CombinedGateFailed("old gate is red"))
        self.assertEqual(owner, book.task("owner"), "accepted cards must never be reopened")
        self.assertNotIn("pending", [row["id"] for row in book.startable()],
                         "an unfinished card cannot spin against a finished owner's defect")

    def test_restart_selects_only_the_first_unfinished_card_of_each_branch(self):
        def row(name, status="todo", needs=(), **extra):
            return {**CODE, "id": name, "status": status, "files": [name + ".py"],
                    "needs": list(needs), **extra}
        rows = [row("root", "sliced", ["finished"]), row("finished", "done"),
                row("left", needs=["root"]), row("right", needs=["finished"]),
                row("later", needs=["left"]), row("held", blocked_by_human=True),
                row("gone", "dropped")]
        book, _ = campaign(rows)
        args = types.SimpleNamespace(lanes=3, max_tasks=0)
        self.assertEqual(["left", "right"], [r["id"] for r in taking_now(book.startable(), args)])

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
