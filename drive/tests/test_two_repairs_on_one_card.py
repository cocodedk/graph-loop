"""Two repairs on one card are approved as they will run: one after the other.

Each was computed against the gate as it stands, so both expected the same
"before" — and the first to land made the second look like a gate somebody had
edited, which stops the activation (an independent review, finding 1). The second's
"before" is the first's "after", in whichever order they were previewed.

And a repaired card goes back to its builder in the SAME write as its gate: the
two were separate, so a death between them left the gate repaired, the card
still rejected, its refund lost — and the repair looking finished (finding 2).
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import triage_routes
from backlog import Backlog
from backlog_status import REBUILD_ROUNDS
from campaigns import campaign
from triage_preview import approve, effects_of
from triage_routes import activate_preview

EXPECTED_TESTS = 5
# A gate both repairs change: `mute-gate` exposes its output, `scrubbed-python`
# points it at the checked-in interpreter.
GATE = ("(cd simulation && timeout 10 python3 -m unittest 2>&1 | "
        "tail -3 | grep -q '^OK')")
CARD = {"id": "T1", "status": "rejected", "goal": "g", "files": ["a.py"], "gate": GATE,
        "rebuild_round": REBUILD_ROUNDS, "gate_rounds": REBUILD_ROUNDS}
LIVE = {"id": "T2", "status": "rejected", "goal": "g", "files": ["b.py"], "gate": GATE,
        "gate_has_side_effects": True}


def previewing(*signatures: str, cards=(CARD,), scope=("T1",)):
    """A campaign previewing these repairs over `scope`, in order, approved."""
    book, space = campaign([dict(one) for one in cards])
    for signature in signatures:
        space.event("triage_sweep", signature=signature, tasks=list(scope),
                    live=[], applied=False)
    space.event("triage_preview", would_alert=[], would_propose=[])
    approve(space, effects_of(book, space.events()) or {}, "preview-2-001")
    return book, space


class TwoRepairsTest(unittest.TestCase):
    def test_the_second_repair_is_approved_on_what_the_first_leaves(self):
        for order in (("mute-gate", "scrubbed-python"),
                      ("scrubbed-python", "mute-gate")):
            with self.subTest(order=order):
                book, space = previewing(*order)
                activate_preview(book, space, space.events())
                gate = book.task("T1")["gate"]
                self.assertIn('echo "$OUT"', gate)          # mute-gate landed
                self.assertIn(".venv/bin/python3", gate)    # and so did the other
                self.assertTrue([one for one in space.events()
                                 if one.get("kind") == "triage_activation"])

    def test_a_gate_edited_between_the_sweeps_stops_the_activation(self):
        """The sweeps before this one told it what the gate would be, so an
        edit that landed in between was invisible and the repair was written
        over text nobody approved (an independent review, finding 1). Each pending
        sweep is checked against the card as it stands."""
        book, space = previewing("mute-gate", "scrubbed-python")
        real = triage_routes.apply_sweep

        def die(book_, space_, index, one):
            if one["signature"] == "scrubbed-python":
                raise ZeroDivisionError("the driver died between the sweeps")
            return real(book_, space_, index, one)

        with mock.patch.object(triage_routes, "apply_sweep", die), \
                self.assertRaises(ZeroDivisionError):
            activate_preview(book, space, space.events())
        edited = book.task("T1")["gate"] + " # somebody's hand"
        book.note("T1", gate=edited)

        activate_preview(book, space, space.events())
        self.assertEqual(edited, book.task("T1")["gate"])     # not repaired
        self.assertEqual([], [one for one in space.events()
                              if one.get("kind") == "triage_activation"])

    def test_a_card_that_stopped_being_live_is_not_swept_on_an_old_approval(self):
        """The approval said T2 was a LIVE match: alerted about, never edited.
        A card that becomes CODE before the activation runs is not the card
        that was approved (an independent review, finding 1)."""
        book, space = previewing("mute-gate", cards=(CARD, LIVE), scope=("T1", "T2"))
        book.note("T2", gate_has_side_effects=None)     # CODE now, nobody reviewed that
        activate_preview(book, space, space.events())
        self.assertEqual(GATE, book.task("T2")["gate"])          # not repaired
        self.assertEqual([], [one for one in space.events()
                              if one.get("kind") == "triage_activation"])

    def test_an_approval_that_says_nothing_about_the_cards_applies_to_nothing(self):
        """An approval written before the loop recorded what each repair would
        find says nothing about the cards, so it matches no card and repairs
        none. A guard that lets missing metadata through repairs whatever they
        have become (an independent review: the earlier version of this test removed
        a key the approval no longer carries, and passed against such a guard)."""
        book, space = previewing("mute-gate")
        path = pathlib.Path(space.root) / "triage-approved"
        older = json.loads(path.read_text("utf-8"))
        for one in older["effects"]["sweeps"]:
            one.pop("facing")                           # as an older writer left it
        path.write_text(json.dumps(older), "utf-8")
        self.assertEqual([False], [("facing" in one) for one
                                   in json.loads(path.read_text("utf-8"))["effects"]["sweeps"]])
        edited = GATE + " # somebody's hand"
        book.note("T1", gate=edited)

        activate_preview(book, space, space.events())
        self.assertEqual(edited, book.task("T1")["gate"])        # not repaired
        self.assertEqual([], [one for one in space.events()
                              if one.get("kind") == "triage_activation"])

    def test_the_gate_and_the_requeue_are_one_write(self):
        """A death in the card write left the gate repaired and the card still
        rejected, with the rounds its broken gate cost never given back — and
        the next turn reading that repaired gate as work already done."""
        book, space = previewing("mute-gate")
        with mock.patch.object(Backlog, "set_status",
                               side_effect=ZeroDivisionError("died in the card write")), \
                self.assertRaises(ZeroDivisionError):
            activate_preview(book, space, space.events())
        card = book.task("T1")
        self.assertEqual(GATE, card["gate"])                 # neither half landed
        self.assertEqual("rejected", card["status"])
        self.assertEqual(REBUILD_ROUNDS, card["rebuild_round"])

        activate_preview(book, space, space.events())        # and the turn after it
        card = book.task("T1")
        self.assertIn('echo "$OUT"', card["gate"])
        self.assertEqual("todo", card["status"])             # requeued with its gate
        self.assertIsNone(card.get("rebuild_round"))         # its rounds given back


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
