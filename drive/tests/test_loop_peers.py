"""A live call frees the cards it held, whatever its ending.

The only release lived inside one refusal branch, so a live call that SUCCEEDED
left every other live card held for ever — and invisibly: the picker offers only
todo, `waiting_for_human` reads only todo, and the hold writes no event. One
successful live task killed the live lane.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from loop_peers import (
    hold_live_peers,
    lost_why,
    open_why,
    release_live_peers,
    restate_live_peers,
)
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 9


class Book:
    """A backlog small enough to read at a glance."""

    def __init__(self, *rows):
        self.rows = list(rows)

    def tasks(self):
        return self.rows

    def set_status(self, task_id, status, **fields):
        row = next(row for row in self.rows if row["id"] == task_id)
        row["status"] = status
        for key, value in fields.items():
            row.pop(key, None) if value is None else row.update({key: value})
        return row


def live(task_id, **extra):
    row = {"id": task_id, "status": "todo", "gate_has_side_effects": True}
    row.update(extra)
    return row


class HoldingAndFreeing(unittest.TestCase):
    def test_every_other_live_card_is_held_while_the_call_is_open(self):
        book = Book(live("T1"), live("T2"), live("T3"))
        self.assertEqual(["T2", "T3"], hold_live_peers(book, "T1", open_why("T1")))
        self.assertEqual(["todo", "held", "held"], [row["status"] for row in book.tasks()])

    def test_a_card_a_person_holds_is_not_this_call_s_to_touch(self):
        book = Book(live("T1"), live("T2", blocked_by_human=True))
        self.assertEqual([], hold_live_peers(book, "T1", open_why("T1")))

    def test_the_end_of_the_call_frees_them(self):
        book = Book(live("T1"), live("T2"), live("T3"))
        hold_live_peers(book, "T1", open_why("T1"))
        self.assertEqual(["T2", "T3"], release_live_peers(book, open_why("T1")))
        self.assertEqual(["todo"] * 3, [row["status"] for row in book.tasks()])
        # released means the hold is gone too, not only the status back to todo
        self.assertEqual([None] * 3, [row.get("blocked_by_human") for row in book.tasks()])

    def test_a_card_held_for_another_reason_stays_held(self):
        book = Book(live("T1"), live("T2", status="held", refused_why="a person said so"))
        self.assertEqual([], release_live_peers(book, open_why("T1")))
        self.assertEqual("held", book.tasks()[1]["status"])

    def test_a_call_that_did_not_return_keeps_them_held(self):
        book = Book(live("T1"), live("T2"))
        hold_live_peers(book, "T1", open_why("T1"))
        self.assertEqual(["T2"], restate_live_peers(book, open_why("T1"), lost_why("T1")))
        self.assertEqual([], release_live_peers(book, open_why("T1")))
        self.assertEqual("held", book.tasks()[1]["status"])


class OneRunnerNeverFreesAnother(unittest.TestCase):
    def test_a_release_frees_only_the_holds_this_task_wrote(self):
        book = Book(live("T1"), live("T2"), live("T3"))
        hold_live_peers(book, "T1", open_why("T1"))
        # T2's own runner has since taken over the doubt about T3
        book.set_status("T3", "held", refused_why=open_why("T2"))
        self.assertEqual(["T2"], release_live_peers(book, open_why("T1")))
        self.assertEqual("held", book.tasks()[2]["status"])   # T3 is not T1's to free


class ThroughTheLoop(unittest.TestCase):
    def test_a_live_card_that_finishes_leaves_no_peer_held(self):
        fakes = Fakes()
        loop, book, _ = loop_for(
            task(gate_has_side_effects=True, gate="grep -q two a.py"), fakes,
            extra=[{"id": "T2", "goal": "another live one", "status": "todo",
                    "needs": [], "files": ["b.py"], "gate": "true",
                    "gate_has_side_effects": True}])
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual("todo", book.task("T2")["status"])
        self.assertIsNone(book.task("T2").get("blocked_by_human"))


class AnExceptionKeepsThemHeld(unittest.TestCase):
    def test_a_call_that_blew_up_leaves_the_doubt_behind(self):
        fakes = Fakes()

        def explode(*args, **kwargs):
            raise RuntimeError("the provider died mid-call")

        loop, book, _ = loop_for(
            task(gate_has_side_effects=True), fakes,
            extra=[{"id": "T2", "goal": "another live one", "status": "todo",
                    "needs": [], "files": ["b.py"], "gate": "true",
                    "gate_has_side_effects": True}])
        loop.build = explode
        with self.assertRaises(RuntimeError):
            loop.run_task(book.task("T1"))
        self.assertEqual("held", book.task("T2")["status"])
        self.assertIn("did not return", book.task("T2")["refused_why"])


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS, found)


if __name__ == "__main__":
    unittest.main()
