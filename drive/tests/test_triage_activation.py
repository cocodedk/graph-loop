"""An approved TRIAGE preview acts once and only on its reviewed scope."""

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
from workspace import Workspace

EXPECTED_TESTS = 6
MUTE_GATE = ("(cd simulation && timeout 10 python3 -m unittest 2>&1 | "
             "tail -3 | grep -q '^OK')")


class ActivationTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        path = self.root / "backlog.yaml"
        path.write_text(yaml.safe_dump({"tasks": [
            {"id": "T1", "status": "todo", "files": ["a.py"], "gate": MUTE_GATE},
            {"id": "T2", "status": "todo", "files": ["b.py"], "gate": MUTE_GATE},
        ]}), "utf-8")
        self.book = Backlog(path)
        self.space = Workspace(self.root / "campaign")

    def boundary(self, task: str) -> None:
        self.space.event("claimed", task=task)
        self.space.artifact(task, "gate-output", "")
        self.space.event("failed", task=task, step="gate")
        self.space.event("released", task=task)

    def approve(self) -> int:
        """Approve exactly the effects the preview would have now: the marker
        names them, so one written for other effects approves nothing."""
        facts = effects_of(self.book, self.space.events()) or {}
        write_approval(self.space, facts)
        return int(facts["index"])

    def test_activation_reuses_a_sweep_completed_before_a_crash(self):
        self.boundary("T1")
        triage_pending(self.book, self.space)
        self.approve()
        real_event = self.space.event

        def crash(kind, **fields):
            if kind == "triage_activation":
                raise RuntimeError("crash")
            return real_event(kind, **fields)

        with (mock.patch.object(self.space, "event", side_effect=crash),
              self.assertRaisesRegex(RuntimeError, "crash")):
            triage_pending(self.book, self.space)
        with mock.patch("triage_routes.apply_sweep") as repeated:
            triage_pending(self.book, self.space)
        repeated.assert_not_called()

    def test_activation_drops_a_route_for_work_finished_after_preview(self):
        action = {"task": "T1", "verdict": "harness", "signature": "provider",
                  "closed_at": "then", "closed_index": 1, "why": "review failed"}
        self.space.event("triage_preview", would_alert=[], would_propose=[action])
        write_approval(self.space, effects_of(self.book, self.space.events()))
        self.book.set_status("T1", "done")
        triage_pending(self.book, self.space)
        self.assertFalse(any(row["kind"] == "triage_proposal"
                             for row in self.space.events()))

    def test_activation_replays_only_the_route_lost_to_a_crash(self):
        alert = {"task": "T1", "verdict": "rig", "signature": "wrong-task",
                 "closed_at": "then", "closed_index": 1, "why": "wrong file"}
        proposal = {"task": "T2", "verdict": "harness", "signature": "provider",
                    "closed_at": "then", "closed_index": 2, "why": "review failed"}
        self.space.event("triage_preview", would_alert=[alert],
                         would_propose=[proposal])
        write_approval(self.space, effects_of(self.book, self.space.events()))
        real_event = self.space.event

        def crash(kind, **fields):
            if kind == "triage_proposal":
                raise RuntimeError("crash")
            return real_event(kind, **fields)

        with (mock.patch.object(self.space, "event", side_effect=crash),
              self.assertRaisesRegex(RuntimeError, "crash")):
            triage_pending(self.book, self.space)
        triage_pending(self.book, self.space)
        rows = self.space.events()
        self.assertEqual(1, sum(row["kind"] == "alert" for row in rows))
        self.assertEqual(1, sum(row["kind"] == "triage_proposal" for row in rows))

    def test_an_unrelated_live_sweep_cannot_suppress_the_approved_scope(self):
        self.boundary("T1")
        triage_pending(self.book, self.space)
        self.book.set_status("T1", "done")
        self.boundary("T2")
        triage_pending(self.book, self.space)
        self.book.set_status("T1", "todo")
        self.approve()
        triage_pending(self.book, self.space)
        self.assertIn('echo "$OUT"', self.book.task("T1")["gate"])

    def test_a_finished_card_is_excluded_from_an_approved_sweep(self):
        self.boundary("T1")
        triage_pending(self.book, self.space)
        self.book.set_status("T1", "done")
        self.approve()
        triage_pending(self.book, self.space)
        self.assertEqual(MUTE_GATE, self.book.task("T1")["gate"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
