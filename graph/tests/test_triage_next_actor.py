"""Every ending TRIAGE can name reaches a next actor.

TRIAGE writes one cause onto the card the loop has just parked, and the pair
(status, cause) is what decides who acts next: the picker, the replan path, or
the plan phase — which re-slices the walls and puts back the cards the harness
parked. The decider used to own whatever those left; it is gone, so the plan
phase owns it. A person is not one of them (CLAUDE.md § Code): an alert is a
message, not a handoff, and a card whose only "actor" was a person on the board
sat until one found it by hand.
Three pairs named nobody — a card whose
red-first gate could not be proved (`green_already`, `unprovable`) carrying the
`contract` cause red-first produces, and a card whose builder wrote outside its
files (`out_of_scope`) carrying the `work` cause a scope failure can be read as.
Those cards sat until a person found them by hand: T26.result.read waited from
its eighth round until 2026-09-08 (commit 8a247c65), which is why the real card
of that morning is this table's `out_of_scope` row.

Each row names where the loop writes that status and where TRIAGE names that
cause, so a row that stops being reachable is visible as a lie rather than as
a passing test.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from backlog_decision import can_replan
from backlog_status import is_wall
from plan_phase import FAULTS, requeue_faults
from replan_budget import MAX_ROUNDS
from triage_effect import repair_effect
from workspace import Workspace

EXPECTED_TESTS = 4
# The card that sat: out_of_scope with cause `work`, a kept worktree and two
# rounds still unspent, and nothing that would ever offer it again. It is the
# out_of_scope/work row of the table below. The card itself stayed with the
# repository whose history holds it.
CODE = {"files": ["a.py"], "gate": "false"}
# (status, cause, who writes the status, what names the cause)
PAIRS = [
    ("green_already", "contract", "loop_evidence: red-first, the gate passed already",
     "triage_signatures: red-first"),
    ("unprovable", "contract", "loop_evidence: red-first could not prove the gate red",
     "triage_signatures: red-first"),
    ("green_already", "environment", "loop_evidence: red-first",
     "triage_signatures: the red-first gate did not run"),
    ("unprovable", "environment", "loop_evidence: red-first",
     "triage_signatures: the red-first gate did not run"),
    ("out_of_scope", "unknown", "loop_steps: the builder wrote outside its files",
     "triage_signatures: scope names no cause, so the plan phase puts it back"),
    ("out_of_scope", "work", "loop_steps: the builder wrote outside its files",
     "triage_intelligence: the model read the paths and blamed the work"),
    ("needs_slice", "work", "loop_judge: the gate failed the same way twice",
     "triage_signatures: repeat-gate"),
    ("needs_slice", "gate", "loop_judge", "triage_signatures: mute-gate"),
    ("needs_slice", "rig", "loop_judge", "triage_signatures: outside-file"),
    ("quarantined", "work", "graph-goal: the watchdog parked a spin",
     "triage_signatures: repeated-ending"),
    ("quarantined", "harness", "graph-goal", "triage_signatures: campaign-futility"),
    ("quarantined", "environment", "graph-goal",
     "triage_signatures: the repeated ending did not run its gate"),
]
# Rows that need a field beyond the status and the cause to be the real thing.
EXTRA = [
    ({"status": "refused_contract", "triage": "contract", "replans": 0},
     "loop_contract refuses; the replan path has both rounds"),
    ({"status": "refused_contract", "triage": "contract", "replans": MAX_ROUNDS},
     "loop_contract refuses; the replan rounds are spent"),
    ({"status": "rejected", "triage": "work", "rebuild_round": 3},
     "loop_judge writes `rejected` only at the round cap"),
    ({"status": "rejected", "triage": "unknown", "rebuild_round": 3},
     "the second unknown on a task; the first buys the one model call"),
    ({"status": "rejected", "triage": "harness", "rebuild_round": 3},
     "loop_judge_retry: the reviewer never answered"),
]


def book_of(row: dict) -> Backlog:
    """One card in its own backlog: `startable` weighs the cards beside it."""
    path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"tasks": [row]}), "utf-8")
    return Backlog(path)


def actor(row: dict, book: Backlog | None = None) -> str:
    """Who acts on this card next, asked of the loop's own four doors: the
    picker, the replanner, TRIAGE's own gate repair, and the plan phase — which
    both re-slices a wall and puts back a card the harness parked.

    An alert used to count here, and it is not an actor: it tells a person, and
    the card waits until one reads it.
    """
    book = book or book_of(row)
    if any(one["id"] == row["id"] for one in book.startable()):
        return "build"
    if can_replan(row):
        return "replan"
    if is_wall(row):
        return "slice"
    if row.get("triage") == "gate" and repair_effect(row, "a different gate").get("status"):
        return "repair"
    if row.get("triage") in FAULTS and not row.get("requeued"):
        return "requeue"
    return ""


class NextActorTest(unittest.TestCase):
    def test_every_status_and_cause_pair_reaches_a_next_actor(self):
        for status, cause, writer, namer in PAIRS:
            with self.subTest(status=status, cause=cause, writer=writer, namer=namer):
                row = {"id": "T1", "status": status, "triage": cause, **CODE}
                self.assertNotEqual("", actor(row))

    def test_every_pair_that_needs_more_than_a_status_reaches_one_too(self):
        for fields, why in EXTRA:
            with self.subTest(why=why, **fields):
                self.assertNotEqual("", actor({"id": "T1", **CODE, **fields}))


class ThePlanPhaseTakesItTest(unittest.TestCase):
    def test_the_plan_phase_actually_puts_back_the_card_the_table_gives_it(self):
        """"requeue" is an actor only because something acts. The route and the
        entry point are asserted together, or this table goes green against a
        name nobody calls — which is exactly what "a person reads the board"
        was, for eleven rounds of T26.result.read.
        """
        row = {"id": "T1", **CODE, "status": "rejected", "triage": "unknown",
               "rebuild_round": 3, "needs": [],
               "refused_why": "the reviewer never answered"}
        book = book_of(row)
        space = Workspace(tempfile.mkdtemp()).init(goal="t", backlog=str(book.path))
        self.assertEqual("requeue", actor(row, book))
        self.assertEqual(1, requeue_faults(book, space))
        back = book.task("T1")
        self.assertEqual("todo", back["status"])
        self.assertNotIn("rebuild_round", back)
        # Once each: a second fault of the same kind on the same card is real.
        self.assertEqual(0, requeue_faults(book, space))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
