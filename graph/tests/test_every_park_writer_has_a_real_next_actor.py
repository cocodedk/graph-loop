"""Every card the loop parks reaches somebody who can take it.

Five places write a card that no picker will offer again: the slicer's
`needs_person` answer and its refusal cap, a live turn that ended badly, a live
call that never started, and the peers a live call held. Each was written for a
person to read, and a person is no longer an actor (CLAUDE.md § Code: the loop
never waits for a person to read or evaluate text) — so each parked card must
reach an existing actor (a picker, the replanner, the slicer), or be dropped
with its gap named, which is what the plan phase does with a hold the LOOP
wrote (`plan_phase.drop_loop_holds`). The decider used to be that actor; it is
gone, and a card it would have taken must still leave the queue.

Four of the five are dropped. The fifth, the slicer's `needs_person` answer, is
the one that ENDS the campaign instead, exactly as the same answer about the
source gap already does (`source_gap.may_try`, whose docstring says why that is
not a wait for a person: the loop stops, it does not block). Leaving the
campaign is leaving the queue; what may not happen is the card sitting in it
looking like work.

Driven through the real writers, not through a copy of what they write.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import types
import unittest

import yaml  # type: ignore[import-untyped]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from loop_peers import hold_live_peers, open_why
from loop_steps_live import live_call_lost
from loop_types import TaskOutcome
from plan_phase import drop_loop_holds
from slice_outcome import MAX_SLICES, record_outcome
from source_ended import unfinished_work
from test_loop import Fakes, loop_for, task
from test_triage_next_actor import actor
from workspace import Workspace

EXPECTED_TESTS = 6
CODE = {"goal": "g", "files": ["a.py"], "gate": "false", "needs": [], "triage": "work"}


def parked(*rows: dict) -> tuple[Backlog, Workspace]:
    path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"tasks": list(rows)}), "utf-8")
    return Backlog(path), Workspace(tempfile.mkdtemp()).init(goal="t", backlog=str(path))


class ParkWriterTest(unittest.TestCase):
    def has_an_actor(self, book: Backlog, task_id: str, space=None) -> None:
        row = book.task(task_id) or {}
        self.assertTrue(row.get("blocked_by_human") or row.get("status") == "live_turn_ended",
                        f"{task_id} was not parked at all: {row}")
        if actor(row, book):
            return
        # Nobody takes it, so the plan phase must take it OUT: the hold is the
        # loop's own, and a card no actor will ever offer is not left in the
        # queue looking like work.
        self.assertEqual("loop", row.get("held_by"), f"{task_id} has no next actor: {row}")
        self.assertTrue(drop_loop_holds(book, space or self.space))
        gone = book.task(task_id)
        self.assertEqual("dropped", gone["status"])
        self.assertTrue(gone.get("refused_why"), "dropped without naming the gap")
        self.assertIsNone(gone.get("blocked_by_human"))

    def test_the_slicer_s_needs_person_answer_ends_the_campaign(self):
        """The fresh review of PR #37, finding 5. Dropped, this refusal became a
        gap the next slicer was asked to close again — and the six-campaign
        report records the same question, on the same tip, answered both ways.
        Re-rolling a die that is known to come up wrong is not a decision, so
        the refusal stands and the campaign ends carrying it."""
        book, space = parked({"id": "W1", "status": "needs_slice", **CODE})
        record_outcome(book, space, "W1", book.task("W1"),
                       "needs_person: the sources do not cover this", 1)

        self.assertTrue(book.task("W1").get("blocked_by_human"))
        self.assertFalse(drop_loop_holds(book, space))       # not the loop's to lift
        self.assertEqual("needs_slice", book.task("W1")["status"])
        gaps = unfinished_work(space, book)
        self.assertEqual(["W1"], [one["id"] for one in gaps])
        self.assertIn("the sources do not cover this", gaps[0]["why"])

    def test_the_slicer_s_refusal_cap_leaves_an_actor(self):
        book, space = parked({"id": "W2", "status": "needs_slice", **CODE})
        for _ in range(MAX_SLICES):
            record_outcome(book, space, "W2", book.task("W2"),
                           "refused: this card cannot be cut smaller", 2)
        self.has_an_actor(book, "W2", space)

    def test_a_live_turn_that_ended_badly_leaves_an_actor(self):
        loop, book, _ = loop_for(task(gate_has_side_effects=True, triage="work"), Fakes())
        loop._through = lambda *args, **kwargs: TaskOutcome("failed", "the gate blew up")
        loop.run_task(book.task("T1"))
        self.assertEqual("live_turn_ended", book.task("T1")["status"])
        self.has_an_actor(book, "T1", loop.space)

    def test_a_live_call_that_never_started_leaves_an_actor(self):
        book, space = parked({"id": "W4", "status": "live_call_open",
                              "gate_has_side_effects": True, **CODE})
        tree = types.SimpleNamespace(path="", remove=lambda: None)
        loop = types.SimpleNamespace(backlog=book, space=space)
        live_call_lost(loop, "W4", tree, types.SimpleNamespace(unstarted=True, kind="limit"),
                       in_place=False)
        self.has_an_actor(book, "W4", space)

    def test_the_peers_a_live_call_held_leave_an_actor(self):
        """Held while its owner runs, the peer is that call's. Once the owner is
        gone — a crash, a call that never came back — the hold is nobody's, and
        the release that would have freed it will never run."""
        book, space = parked({"id": "W5", "status": "todo", "gate_has_side_effects": True,
                              **CODE},
                             {"id": "W6", "status": "todo", "gate_has_side_effects": True,
                              **CODE})
        self.assertEqual(["W6"], hold_live_peers(book, "W5", open_why("W5")))
        self.has_an_actor(book, "W6", space)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
