"""TRIAGE coordinates durable endings without turning into another loop."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from triage import triage_pending
from triage_preview import approve as write_approval
from triage_preview import effects_of
from triage_signatures import Decision
from workspace import Workspace

EXPECTED_TESTS = 9
MUTE_GATE = ("(cd simulation && timeout 10 python3 -m unittest 2>&1 | "
             "tail -3 | grep -q '^OK')")


class TriageTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.path = self.root / "backlog.yaml"
        tasks = [
            {"id": "T1", "status": "todo", "files": ["a.py"],
             "gate": MUTE_GATE, "triage": "old"},
            {"id": "T2", "status": "todo", "files": ["b.py"],
             "gate": "false", "triage": "old"},
            {"id": "T3", "status": "done", "files": ["c.py"],
             "gate": MUTE_GATE, "triage": "old"},
            {"id": "T4", "status": "todo", "files": ["d.py"],
             "gate": "false"},
            {"id": "T5", "status": "todo", "files": ["e.py"],
             "gate": "false"},
        ]
        self.path.write_text(yaml.safe_dump({"tasks": tasks}), "utf-8")
        self.book = Backlog(self.path)
        self.space = Workspace(self.root / "campaign")

    def boundary(self, task: str, *events: dict, output: str | None = None) -> None:
        self.space.event("claimed", task=task)
        if output is not None:
            self.space.artifact(task, "gate-output", output)
        for event in events:
            row = dict(event)
            self.space.event(str(row.pop("kind")), task=task, **row)
        self.space.event("released", task=task)

    def test_first_catchup_records_all_boundaries_and_previews_every_action(self):
        self.boundary("T1", {"kind": "failed", "step": "gate"}, output="")
        self.boundary("T1", {"kind": "worktree"})  # advances, never clears
        self.boundary("T2", {"kind": "accepted"})
        self.boundary("T3", {"kind": "failed", "step": "gate"}, output="")
        self.boundary("T4", {"kind": "review_unavailable"})
        self.boundary("T5", {"kind": "failed", "step": "gate"},
                      output="tests/other.py failed")
        forbidden = mock.Mock(side_effect=AssertionError("first catch-up spent money"))
        with mock.patch.object(self.book, "note", wraps=self.book.note) as write:
            found = triage_pending(self.book, self.space, call=forbidden)

        self.assertEqual(6, len(found))
        self.assertEqual(4, write.call_count)  # open cards once; never T3
        self.assertEqual("gate", self.book.task("T1")["triage"])
        self.assertNotIn("triage", self.book.task("T2"))
        self.assertEqual("old", self.book.task("T3")["triage"])
        self.assertEqual(MUTE_GATE, self.book.task("T1")["gate"])
        rows = self.space.events()
        triage = [row for row in rows if row["kind"] == "triage"]
        self.assertEqual(["gate", None, None, "gate", "harness", "rig"],
                         [row["verdict"] for row in triage])
        self.assertEqual(["gate", "unchanged", "cleared", "unchanged",
                          "harness", "rig"], [row["card"] for row in triage])
        self.assertEqual("no outcome in this boundary", triage[1]["why"])
        [sweep] = [row for row in rows if row["kind"] == "triage_sweep"]
        self.assertFalse(sweep["applied"])
        [preview] = [row for row in rows if row["kind"] == "triage_preview"]
        self.assertEqual(["T5"], [row["task"] for row in preview["would_alert"]])
        self.assertEqual(["T4"], [row["task"] for row in preview["would_propose"]])
        self.assertEqual([], self.space.alerts(False))
        self.assertFalse(any(row["kind"] == "triage_proposal" for row in rows))

        triage_pending(self.book, self.space)
        self.assertEqual(MUTE_GATE, self.book.task("T1")["gate"])
        self.assertEqual(1, len(self.space.alerts(False)))
        self.book.set_status("T3", "todo")  # not part of the reviewed preview
        write_approval(self.space, effects_of(self.book, self.space.events()))
        triage_pending(self.book, self.space)
        self.assertIn('echo "$OUT"', self.book.task("T1")["gate"])
        self.assertEqual(MUTE_GATE, self.book.task("T3")["gate"])
        rows = self.space.events()
        self.assertEqual(["T4"], [row["task"] for row in rows
                                  if row["kind"] == "triage_proposal"])
        self.assertTrue(any("T5" in line for line in self.space.alerts(False)))
        self.assertEqual(1, sum(row["kind"] == "triage_activation" for row in rows))

    def test_an_empty_first_turn_is_still_recorded(self):
        self.assertEqual([], triage_pending(self.book, self.space))
        [preview] = [row for row in self.space.events()
                     if row["kind"] == "triage_preview"]
        self.assertEqual(([], []),
                         (preview["would_alert"], preview["would_propose"]))

    def test_a_later_first_unknown_uses_the_plan_belt_once(self):
        self.boundary("T2", {"kind": "accepted"})
        triage_pending(self.book, self.space)
        self.boundary("T1", {"kind": "failed", "step": "gate"},
                      output="one clear assertion failed")
        answer = Decision("rig", "model", "the fixture is wrong")
        with mock.patch("triage.decide_unknown", return_value=answer) as decide:
            found = triage_pending(self.book, self.space, call=object())
        self.assertEqual("rig", found[0].verdict)
        decide.assert_called_once()
        self.assertEqual("rig", self.book.task("T1")["triage"])
        self.assertTrue(any("T1" in line and "needs a person" in line
                            for line in self.space.alerts(False)))
        self.boundary("T1", {"kind": "failed", "step": "gate"},
                      output="a later unmatched assertion")
        with mock.patch("triage.decide_unknown") as repeated:
            triage_pending(self.book, self.space)
        repeated.assert_not_called()

    def test_a_spent_unknown_call_alerts_without_waiting_for_another_ending(self):
        self.boundary("T2", {"kind": "accepted"})
        triage_pending(self.book, self.space)
        self.boundary("T1", {"kind": "failed", "step": "gate"},
                      output="one clear assertion failed")
        answer = Decision("unknown", "model-unavailable", "the belt did not answer")
        with mock.patch("triage.decide_unknown", return_value=answer):
            triage_pending(self.book, self.space)
        self.assertTrue(any("needs a person" in line
                            for line in self.space.alerts(False)))

    def test_a_second_unknown_alerts_without_another_model_call(self):
        self.boundary("T1", {"kind": "failed", "step": "gate"},
                      output="first clear assertion")
        triage_pending(self.book, self.space)
        self.boundary("T1", {"kind": "failed", "step": "gate"},
                      output="different clear assertion")
        with mock.patch("triage.decide_unknown") as decide:
            triage_pending(self.book, self.space)
        decide.assert_not_called()
        self.assertEqual("unknown", self.book.task("T1")["triage"])
        self.assertTrue(any("unknown twice" in line
                            for line in self.space.alerts(False)))

    def test_a_later_confirmed_repair_is_applied(self):
        self.boundary("T2", {"kind": "accepted"})
        triage_pending(self.book, self.space)
        self.boundary("T1", {"kind": "failed", "step": "gate"}, output="")
        self.boundary("T4", {"kind": "failed", "step": "gate"}, output="")
        triage_pending(self.book, self.space)
        card = self.book.task("T1")
        self.assertIn('echo "$OUT"', card["gate"])
        self.assertTrue(card["gate_reviewed_first"])
        sweeps = [row for row in self.space.events() if row["kind"] == "triage_sweep"]
        self.assertTrue(sweeps[-1]["applied"])
        self.assertTrue(any("T4" in line and "mute-gate" in line
                            for line in self.space.alerts(False)))

    def test_only_each_tasks_latest_boundary_can_propose(self):
        self.boundary("T2", {"kind": "accepted"})
        triage_pending(self.book, self.space)
        self.boundary("T1", {"kind": "review_unavailable"})
        self.boundary("T1", {"kind": "accepted"})
        self.boundary("T4", {"kind": "review_unavailable"})
        triage_pending(self.book, self.space)
        proposals = [row for row in self.space.events()
                     if row["kind"] == "triage_proposal"]
        self.assertEqual(["T4"], [row["task"] for row in proposals])

    def test_no_op_card_updates_are_recorded_as_unchanged(self):
        self.book.set_status("T5", "todo", triage="rig")
        self.boundary("T4", {"kind": "accepted"})
        self.boundary("T5", {"kind": "failed", "step": "gate"},
                      output="tests/other.py failed")
        triage_pending(self.book, self.space)
        rows = [row for row in self.space.events() if row["kind"] == "triage"]
        self.assertEqual(["unchanged", "unchanged"],
                         [row["card"] for row in rows])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
