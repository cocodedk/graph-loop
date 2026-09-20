"""The plan phase slices until the graph stops growing, and then stops.

Exhaustion is read from the backlog, never from what a slicer call said about
itself: a call that answers `published:` and writes no card is a round that
added nothing, and a phase that believed the answer would slice for ever.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import plan_phase
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from finishing import SOURCE_GAP  # plan_phase reads the record through `finishing`

EXPECTED_TESTS = 10


def vault(*names: str) -> Backlog:
    root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
    root.mkdir(parents=True)
    for name in names:
        _add(root, name)
    return Backlog(root)


def _add(root: pathlib.Path, name: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / cardfile.HEAD).write_text(
        cardfile.dump({"status": "todo", "goal": "g"}), "utf-8")


class Space:
    """Enough workspace for the phase: it only records what it added."""

    def __init__(self):
        self.root = tempfile.mkdtemp()
        self.events_written: list[dict] = []

    def event(self, kind, **fields):
        self.events_written.append({"kind": kind, **fields})

    def events(self):
        return list(self.events_written)


class ThePhaseEndsWhenTheGraphStops(unittest.TestCase):
    def setUp(self):
        self.book, self.space = vault("T1"), Space()

    def sliced(self, *rounds: tuple):
        """One slicer stand-in per round; each names the molecules it adds."""
        calls = list(rounds)

        def slicing(book, space, taking=()):
            for name in calls.pop(0) if calls else ():
                _add(book.path, name)
        return slicing

    def test_a_round_that_adds_nothing_ends_the_phase(self):
        with unittest.mock.patch.object(plan_phase, "slice_pending",
                                        self.sliced(("T2",), ())):
            self.assertEqual(1, plan_phase.plan(self.book, self.space))

    def test_the_phase_keeps_going_while_cards_keep_landing(self):
        with unittest.mock.patch.object(plan_phase, "slice_pending",
                                        self.sliced(("T2",), ("T3", "T4"), ())):
            self.assertEqual(3, plan_phase.plan(self.book, self.space))

    def test_a_slicer_that_writes_no_card_is_one_round_and_no_more(self):
        called = []
        with unittest.mock.patch.object(
                plan_phase, "slice_pending",
                lambda book, space, taking=(): called.append(1)):
            self.assertEqual(0, plan_phase.plan(self.book, self.space))
        self.assertEqual(1, len(called))

    def test_a_failed_slice_is_not_exhaustion(self):
        """One card that cannot be sliced used to end the whole phase.

        A card was written whose gate could not pass inside its own file grant,
        so every re-slice of it was refused; it added no card, the round looked
        barren, and the phase stopped — with every other wall unplanned and the
        source gap never reached. A failed attempt is not nothing: it spends one
        of the card's three, and after the third the card is held and the next
        wall is the target. Exhaustion is the round that changes NOTHING
        (2026-09-18, the first real campaign run)."""
        rounds = [lambda: self.book.note("T1", slices=1),
                  lambda: _add(self.book.path, "T2"),
                  lambda: None]

        def slicing(book, space, taking=()):
            if rounds:
                rounds.pop(0)()

        with unittest.mock.patch.object(plan_phase, "slice_pending", slicing):
            self.assertEqual(1, plan_phase.plan(self.book, self.space))
        self.assertEqual([], rounds, "the phase stopped on the barren round")

    def test_rounds_stops_the_phase_early(self):
        with unittest.mock.patch.object(plan_phase, "slice_pending",
                                        self.sliced(("T2",), ("T3",), ("T4",))):
            self.assertEqual(1, plan_phase.plan(self.book, self.space, rounds=1))

    def test_what_each_round_added_is_recorded(self):
        with unittest.mock.patch.object(plan_phase, "slice_pending",
                                        self.sliced(("T2",), ())):
            plan_phase.plan(self.book, self.space)
        # `plan_started` first: it is what opens the window the driver's own
        # stand-down reads coverage in (`finishing.covered_since_planning`), so
        # the phase writes it before it plans anything.
        self.assertEqual([{"kind": "plan_started"},
                          {"kind": "planned", "task": "the plan", "added": ["T2"]}],
                         self.space.events_written)


class ThePhaseSaysWhetherTheGraphIsFinished(unittest.TestCase):
    """A refused round and a finished graph both add no card.

    Two runs ended with `the plan added 8 cards` and exit 0 on a graph that was
    plainly unfinished — the branches were named `paste-link-shows-text` and
    `share-link-shows-text` and nothing that showed anything had been planned.
    What actually stopped it was in the slicer's trace: three validator
    refusals in a row. A phase that cannot tell "the planner found no gap" from
    "the planner could not answer" reports every failure as success
    (2026-09-18, both campaign runs).
    """

    def setUp(self):
        self.book, self.space = vault("T1"), Space()

    def test_a_gap_the_planner_closed_is_finished(self):
        self.space.events_written.append(
            {"kind": "slice_finished", "task": SOURCE_GAP,
             "rc": 0, "state": "covered"})
        self.assertEqual((True, ""), plan_phase.finished(self.book, self.space))

    def test_a_gap_slice_that_wrote_a_molecule_has_not_closed_the_gap(self):
        """It finished cleanly and it found work: that is the opposite of done."""
        self.space.events_written.append(
            {"kind": "slice_finished", "task": SOURCE_GAP,
             "rc": 0, "state": "published"})
        self.assertFalse(plan_phase.finished(self.book, self.space)[0])

    def test_a_capped_gap_is_not_finished_and_says_so(self):
        self.space.events_written.append(
            {"kind": "slice_gap_capped", "task": SOURCE_GAP, "count": 3})
        done, why = plan_phase.finished(self.book, self.space)
        self.assertFalse(done)
        self.assertIn("source", why)

    def test_a_gap_nobody_ever_closed_is_not_finished(self):
        """No capped event either — the phase simply never got an answer."""
        done, why = plan_phase.finished(self.book, self.space)
        self.assertFalse(done)
        self.assertIn("source", why)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
