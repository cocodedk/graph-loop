"""A successful slice does not cover what the source gap said afterwards.

Codex's review: the proof only moved on `driver_started` and `slice_finished`,
so a slice that succeeded early in a run left its proof standing over everything
that came later — a gap that asked for a person, a turn whose checkout could not
be cut, or a person redeclaring the sources under it. The proof is about the
LAST thing the source gap said, not about anything having once gone well.

The fresh review of the phase split, finding 1: that boundary was
`driver_started`, and after the split no slice can follow it, so `run` could
never exit 0. The window belongs to the phase that actually slices, and its
last word has to be `covered` — a gap slice that PUBLISHED a molecule also
finishes cleanly, and that is the planner finding a gap, not closing it.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from finishing import covered_since_planning
from slice_outcome import record_outcome
from workspace import Workspace
from finishing import ENDED_WITH_GAPS, stand_down
from slicer_state import close
import cardfile
import source_gap
import where

EXPECTED_TESTS = 5


def campaign() -> tuple[Workspace, Backlog]:
    """A plan phase that has run and closed the source gap."""
    root = pathlib.Path(tempfile.mkdtemp())
    tree = root / "tree"
    tree.mkdir()
    space = Workspace(root / "campaign").init(goal="the backlog", backlog=str(tree))
    space.event("sources_declared", sources=["README.md"])
    space.event("plan_started")
    book = Backlog(tree)
    record_outcome(book, space, "the sources", None,
                   "covered: approved sources are unchanged", 0)
    assert covered_since_planning(space)
    return space, book


class ClearedTest(unittest.TestCase):
    def test_new_coverage_does_not_finish_an_unsettled_backlog(self):
        space, book = campaign()
        (book.path / "owed").mkdir()
        (book.path / "owed" / "molecule.md").write_text(cardfile.dump({
            "id": "owed", "status": "rejected", "goal": "the source claim",
            "files": ["a.py"], "gate": "true", "done_when": "proved"}), "utf-8")
        source_gap.end_with_gaps(space, book, "", {"gap": "the source claim"})
        close(book.path, [where.loop() / "README.md"], "accepted", where.loop(), book.tasks())
        record_outcome(book, space, "the sources", None, "covered: reviewed", 0)
        self.assertEqual(ENDED_WITH_GAPS, stand_down(space, book))
        self.assertIn("owed", source_gap.ended(space)["gaps"])

    def test_a_gap_that_then_asks_for_a_person_clears_the_proof(self):
        space, book = campaign()
        record_outcome(book, space, "the sources", None,
                       "needs_person: the source asks for a method no gate can observe", 2)

        self.assertFalse(covered_since_planning(space))

    def test_a_turn_that_could_not_slice_at_all_clears_the_proof(self):
        space, _ = campaign()
        # the shape `slice_turn` records when it cannot cut a clean checkout
        space.event("slice_skipped", task="the sources",
                    why="the campaign branch campaign/graph cannot be resolved")

        self.assertFalse(covered_since_planning(space))

    def test_redeclared_sources_clear_the_proof(self):
        space, _ = campaign()
        space.event("sources_declared", sources=["README.md", "CONTRIBUTING.md"])

        self.assertFalse(covered_since_planning(space))

    def test_a_gap_slice_that_published_a_molecule_is_not_coverage(self):
        """It exits 0 and it finished cleanly, and it says the opposite of
        covered: the planner found a gap and cut a card out of it."""
        space, book = campaign()
        record_outcome(book, space, "the sources", None, "published: greeting", 0)

        self.assertFalse(covered_since_planning(space))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
