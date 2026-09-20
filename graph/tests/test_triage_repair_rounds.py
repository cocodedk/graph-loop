"""A repaired card whose rounds are spent is either given them back or handed
to a person — never left `todo` where nothing will offer it.

The requeue writes `todo` whatever the rounds say, and the picker refuses a
card that has spent them (`backlog.ready`). So a repair could land on a card
the loop had already exhausted and leave it looking ready and reachable by
nobody. What comes back is `gate_rounds`, the count written where a gate
failure CHARGES a round (`loop_judge_retry._send_back`) — never the journal's
failures, which cannot say whether a round was charged at all. T8 carries two
of those failures for exactly that reason: they are here to be ignored. A card
still exhausted after the refund had rounds the gate did not cost, so a person
is told.
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
from test_triage_repair_requeue import MUTE_GATE
from triage_repairs import sweep
from workspace import Workspace

EXPECTED_TESTS = 4


def card(task_id: str, path: str, gate_rounds: int = 0) -> dict:
    """Three rounds spent, `gate_rounds` of them charged by the gate itself —
    the counter `loop_judge_retry._send_back` writes where it charges one."""
    row = {"id": task_id, "status": "rejected", "triage": "gate", "rebuild_round": 3,
           "files": [path], "gate": MUTE_GATE}
    return {**row, "gate_rounds": gate_rounds} if gate_rounds else row


class SpentRoundsTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        path = self.root / "backlog.yaml"
        # T6 spent all three on the gate, T7 none of them, T8 one: its other
        # two went on a review finding and on a second identical gate failure,
        # which parks a card as `needs_slice` and charges nothing.
        path.write_text(yaml.safe_dump({"tasks": [
            card("T6", "f.py", 3), card("T7", "g.py"), card("T8", "h.py", 1)]}), "utf-8")
        self.book = Backlog(path)
        self.space = Workspace(self.root / "campaign")
        for _ in range(2):     # T8's two failures are on the journal; one cost a round
            self.space.event("failed", task="T8", step="gate", why="the gate printed nothing")

    def test_the_rounds_the_broken_gate_cost_come_back_with_the_repair(self):
        sweep(self.book, self.space, "mute-gate")
        row = self.book.task("T6")
        self.assertEqual("todo", row["status"])
        self.assertNotIn("rebuild_round", row)               # all three were the gate's
        self.assertEqual(3, row["gate_rounds_refunded"])     # and the card says so
        self.assertIn("T6", [ready["id"] for ready in self.book.startable()])

    def test_rounds_the_gate_never_cost_are_a_person_s_to_decide(self):
        sweep(self.book, self.space, "mute-gate")
        row = self.book.task("T7")
        self.assertEqual("rejected", row["status"])          # not left todo and unreachable
        self.assertTrue([line for line in self.space.alerts() if "T7" in line])

    def test_only_the_rounds_the_gate_was_charged_for_come_back(self):
        """A failure event is not a charged round. Counting the journal's two
        refunded the review rejection too, and bought the card back a round its
        builder had spent on a finding the repair does not answer."""
        sweep(self.book, self.space, "mute-gate")
        row = self.book.task("T8")
        self.assertEqual(2, row["rebuild_round"])            # the review round stands
        self.assertEqual(1, row["gate_rounds_refunded"])

    def test_a_second_repair_does_not_refund_the_same_failures_twice(self):
        sweep(self.book, self.space, "mute-gate")
        self.book.set_status("T6", "rejected", rebuild_round=3)   # three review rejections since
        sweep(self.book, self.space, "scrubbed-python")
        row = self.book.task("T6")
        self.assertEqual("rejected", row["status"])
        self.assertEqual(3, row["rebuild_round"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
