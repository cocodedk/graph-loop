"""A repaired gate goes back to its builder, keeping the paid work and the hold.

TRIAGE repairs a gate only when the repair actually changes it, so the card is
not the refusal it was — but the repair wrote the gate and left the status
alone, so a card parked as `unprovable` (or any other ending) kept its parked
status and nothing ever offered it again. The repair was silent progress that
reached nobody.

Two things the requeue must not take with it: the kept worktree of a paid round
(`rebuild_from`), and a hold a person put on the card — `Backlog._apply` clears
`blocked_by_human` on any write of `todo`, so a held card is repaired where it
stands and stays the person's.
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
from backlog_status import is_wall
from triage_repairs import sweep
from workspace import Workspace

EXPECTED_TESTS = 6
MUTE_GATE = ("(cd simulation && timeout 10 python3 -m unittest 2>&1 | "
             "tail -3 | grep -q '^OK')")
TREE = "/tmp/drive-r7yatfqy/task-T1"


class RequeueTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        path = self.root / "backlog.yaml"
        path.write_text(yaml.safe_dump({"tasks": [
            {"id": "T1", "status": "unprovable", "files": ["a.py"], "gate": MUTE_GATE,
             "triage": "gate", "rebuild_from": TREE, "rebuild_round": 1,
             "refused_why": "gate not proved red: the gate printed nothing"},
            {"id": "T2", "status": "unprovable", "files": ["b.py"], "gate": MUTE_GATE,
             "triage": "gate", "blocked_by_human": True},
            {"id": "T3", "status": "sliced", "files": ["c.py"], "gate": MUTE_GATE,
             "needs": ["T3.a"], "triage": "gate"},
            {"id": "T3.a", "status": "todo", "files": ["d.py"], "gate": "false",
             "sliced_from": "T3"},
            {"id": "T4", "status": "rejected", "triage": "work", "rebuild_round": 3,
             "files": ["e.py"], "gate": MUTE_GATE},
            {"id": "T5", "status": "refused_contract", "triage": "contract", "replans": 0,
             "files": ["f.py"], "gate": MUTE_GATE},
        ]}), "utf-8")
        self.book = Backlog(path)
        self.space = Workspace(self.root / "campaign")

    def test_a_repaired_card_is_offered_to_its_builder_with_its_worktree(self):
        self.assertIn("T1", sweep(self.book, self.space, "mute-gate"))
        card = self.book.task("T1")
        self.assertEqual("todo", card["status"])
        self.assertEqual(TREE, card["rebuild_from"])        # the round it paid for
        self.assertEqual(1, card["rebuild_round"])          # and what that round cost
        self.assertIn("T1", [row["id"] for row in self.book.startable()])
        # the reason it was parked describes a gate that no longer exists, and
        # every other requeue in the loop clears it (replan, back_in_place)
        self.assertNotIn("refused_why", card)

    def test_a_held_card_is_repaired_where_it_stands(self):
        self.assertIn("T2", sweep(self.book, self.space, "mute-gate"))
        card = self.book.task("T2")
        self.assertTrue(card["blocked_by_human"])
        self.assertEqual("unprovable", card["status"])
        self.assertNotEqual(MUTE_GATE, card["gate"])        # repaired all the same

    def test_a_sliced_parent_is_repaired_without_being_offered_again(self):
        """Its work lives in its pieces now. `settled` reads `sliced`, so a
        parent written back to `todo` never settles and everything that needs
        it waits for ever — and once its pieces are done the picker offers the
        parent's own work a second time."""
        self.assertIn("T3", sweep(self.book, self.space, "mute-gate"))
        self.assertEqual("sliced", self.book.task("T3")["status"])

    def test_a_card_the_slicer_already_owns_keeps_its_actor(self):
        """The sweep repairs every open card the repair changes, not only the
        one whose ending fired it. A wall requeued to `todo` is offered by
        nobody — its rounds are spent — and is no longer a wall either, so the
        repair would take a card from the slicer and hand it to a person."""
        self.assertIn("T4", sweep(self.book, self.space, "mute-gate"))
        self.assertTrue(is_wall(self.book.task("T4")))

    def test_a_refused_contract_stays_the_replan_path_s(self):
        """A gate repair exposes what a gate printed; it does not answer "this
        gate can pass without the work", which is what the reviewer refused.
        Requeued, the card would be built against the contract the reviewer
        turned down and be refused again one paid review later."""
        self.assertIn("T5", sweep(self.book, self.space, "mute-gate"))
        self.assertEqual("refused_contract", self.book.task("T5")["status"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
