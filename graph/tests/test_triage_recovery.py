"""TRIAGE reuses durable decisions after a crash and never repays a call."""

from __future__ import annotations

import pathlib
import stat
import sys
import tempfile
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import cardfile
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from triage import triage_pending
from triage_cards import write_cards
from triage_evidence import Ending
from triage_signatures import Decision
from triage_state import valid_decision
from workspace import Workspace

EXPECTED_TESTS = 10
MUTE_GATE = ("(cd simulation && timeout 10 python3 -m unittest 2>&1 | "
             "tail -3 | grep -q '^OK')")


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        path = self.root / "backlog.yaml"
        path.write_text(yaml.safe_dump({"tasks": [
            {"id": "T1", "status": "todo", "files": ["a.py"],
             "gate": MUTE_GATE, "triage": "old"},
            {"id": "T2", "status": "todo", "files": ["b.py"], "gate": "false"},
        ]}), "utf-8")
        self.book = Backlog(path)
        self.space = Workspace(self.root / "campaign")

    def boundary(self, output: str) -> None:
        self.space.event("claimed", task="T1")
        self.space.artifact("T1", "gate-output", output)
        self.space.event("failed", task="T1", step="gate")
        self.space.event("released", task="T1")

    def test_an_incomplete_catchup_stays_a_preview_and_reuses_its_write(self):
        self.boundary("")
        with (mock.patch("triage._record", side_effect=RuntimeError("crash")),
              self.assertRaisesRegex(RuntimeError, "crash")):
            triage_pending(self.book, self.space)
        rows = self.space.events()
        self.assertTrue(any(row["kind"] == "triage_decision" for row in rows))
        self.assertFalse(any(row["kind"] == "triage_preview" for row in rows))
        with mock.patch.object(self.book, "note",
                               wraps=self.book.note) as write:
            triage_pending(self.book, self.space)
        self.assertEqual(0, write.call_count)
        self.assertEqual(1, sum(row["kind"] == "triage_preview"
                                for row in self.space.events()))

    def test_a_model_decision_survives_a_crash_after_the_call(self):
        triage_pending(self.book, self.space)  # complete the empty first catch-up
        self.boundary("one clear assertion")
        answer = Decision("rig", "model", "the fixture is wrong")
        with (mock.patch("triage.decide_unknown", return_value=answer) as decide,
              mock.patch("triage._write_cards", side_effect=RuntimeError("crash")),
              self.assertRaisesRegex(RuntimeError, "crash")):
            triage_pending(self.book, self.space)
        decide.assert_called_once()
        rows = self.space.events()
        self.assertEqual(1, sum(row["kind"] == "triage_model" for row in rows))
        self.assertTrue(any(row["kind"] == "triage_decision"
                            and row["verdict"] == "rig" for row in rows))
        with mock.patch("triage.decide_unknown",
                        side_effect=AssertionError("model repeated")):
            triage_pending(self.book, self.space)
        self.assertEqual("rig", self.book.task("T1")["triage"])

    def test_a_crash_after_the_model_marker_queues_a_person_without_repaying(self):
        triage_pending(self.book, self.space)
        self.boundary("one clear assertion")
        with (mock.patch("triage.decide_unknown", side_effect=RuntimeError("crash")),
              self.assertRaisesRegex(RuntimeError, "crash")):
            triage_pending(self.book, self.space)
        with mock.patch("triage.decide_unknown") as repeated:
            triage_pending(self.book, self.space)
        repeated.assert_not_called()
        self.assertEqual(1, sum(row["kind"] == "triage_model"
                                for row in self.space.events()))
        self.assertTrue(any("needs a person" in line
                            for line in self.space.alerts(False)))

    def test_a_tree_card_write_preserves_legacy_child_links(self):
        tree = self.root / "tree"
        parent, child = tree / "T6" / "molecule.md", tree / "T6.child" / "molecule.md"
        parent.parent.mkdir(parents=True)
        child.parent.mkdir(parents=True)
        # Hand-edited: a comment, CRLF endings, prose. Only the verdict may move.
        original = ("---\r\n# keep this exact layout\r\nstatus: sliced\r\nneeds:\r\n"
                    "  - T2  # external parent\r\n  - T6.child\r\n---\r\n\r\n"
                    "## Goal\r\n\r\nthe piece\r\n")
        with parent.open("w", encoding="utf-8", newline="") as handle:
            handle.write(original)
        parent.chmod(0o640)
        child.write_text(cardfile.dump({"status": "done", "sliced_from": "T6"}), "utf-8")
        book, space = Backlog(tree), Workspace(self.root / "tree-campaign")
        space.event("claimed", task="T6")
        space.event("failed", task="T6", step="scope")
        space.event("released", task="T6")
        triage_pending(book, space)
        with parent.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        raw = cardfile.parse(text)
        self.assertEqual(["T2", "T6.child"], raw["needs"])
        self.assertEqual("unknown", raw["triage"])   # a scope refusal names no cause
        self.assertEqual(original.replace("  - T6.child\r\n---",
                                          "  - T6.child\r\ntriage: unknown\r\n---"), text)
        self.assertEqual(0o640, stat.S_IMODE(parent.stat().st_mode))

    def test_damaged_state_replays_without_inventing_a_second_unknown(self):
        self.boundary("one clear assertion")
        triage_pending(self.book, self.space)
        rows = self.space.events()
        decision = [row for row in rows if row["kind"] == "triage_decision"][-1]
        cursor = [row for row in rows if row["kind"] == "triage"][-1]
        self.space.event("triage_decision", **{
            key: value for key, value in decision.items() if key not in ("at", "kind")
        } | {"verdict": "not-a-verdict"})
        self.space.event("triage", task="T1", verdict=None,
                         closed_at=cursor["closed_at"], closed_index="damaged",
                         closed_kind=cursor["closed_kind"])
        triage_pending(self.book, self.space)
        self.assertEqual("unknown", self.book.task("T1")["triage"])
        self.assertFalse(any("unknown twice" in line
                             for line in self.space.alerts(False)))

    def test_a_live_sweep_is_not_repeated_after_a_crash_before_the_cursor(self):
        triage_pending(self.book, self.space)
        self.boundary("")
        with (mock.patch("triage._record", side_effect=RuntimeError("crash")),
              self.assertRaisesRegex(RuntimeError, "crash")):
            triage_pending(self.book, self.space)
        triage_pending(self.book, self.space)
        applied = [row for row in self.space.events()
                   if row["kind"] == "triage_sweep" and row["applied"]]
        self.assertEqual(1, len(applied))

    def test_a_malformed_later_decision_cannot_hide_a_preview_route(self):
        self.space.event("claimed", task="T1")
        self.space.event("review_unavailable", task="T1")
        self.space.event("released", task="T1")
        with (mock.patch("triage._record", side_effect=RuntimeError("crash")),
              self.assertRaisesRegex(RuntimeError, "crash")):
            triage_pending(self.book, self.space)
        self.space.event("triage_decision", task="T1", verdict=None, catchup=True)
        triage_pending(self.book, self.space)
        [preview] = [row for row in self.space.events()
                     if row["kind"] == "triage_preview"]
        self.assertEqual(["T1"], [row["task"]
                                  for row in preview["would_propose"]])

    def test_a_decision_accepts_only_the_platform_turn_provenance(self):
        row = self.space.event(
            "triage_decision", task="T1", verdict="gate", signature="mute-gate",
            why="the gate was silent", repairable=True, catchup=False,
            accepted=False, closed_at="2026-09-01T00:00:00Z", closed_index=7,
            closed_kind="released", turn="turn-7",
        )
        self.assertTrue(valid_decision(row))
        row["unexpected"] = "untrusted"
        self.assertFalse(valid_decision(row))


    def test_a_held_todo_card_gets_its_verdict_without_losing_the_hold(self):
        """write_cards must not use set_status: echoing the card's own todo
        status back to it would trip the requeue default and clear the hold."""
        path = self.root / "held.yaml"
        path.write_text(yaml.safe_dump({"tasks": [
            {"id": "T9", "status": "todo", "files": ["a.py"], "gate": "true",
             "blocked_by_human": True},
        ]}), "utf-8")
        book = Backlog(path)
        ending = Ending("T9", {}, (), {}, ())
        write_cards(book, [ending], [Decision("work", "sig", "why")])
        self.assertEqual("work", book.task("T9")["triage"])
        self.assertTrue(book.task("T9")["blocked_by_human"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
