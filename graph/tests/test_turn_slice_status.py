"""The turn-top slicer call's stale-status guard, split from test_turn_slice
at the 200-line cap. The rig is test_turn_slice's."""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import slice_turn
from test_turn_slice import routed, router, space, tree_with

EXPECTED_TESTS = 2


class StatusRetainedTest(unittest.TestCase):
    def test_a_stored_status_change_survives_a_refused_slice(self):
        # target is picked once at the top of slice_pending; a status write
        # that lands on disk during the slicer call must not be clobbered
        # back to the picked-time value once the outcome is recorded. Since
        # astra round 4 finding 2 it survives more strongly: the answer was
        # decided from the older card, so nothing of it is written at all and
        # the round is not charged — the same `card_moved` the slicer's own
        # publication already refuses with. `note()` writing fields without
        # restating a status (fix A5, e74a0270) has its own witness in
        # `test_backlog.NoteTest`.
        book = tree_with({"id": "T1", "status": "needs_slice", "goal": "g",
                          "files": ["a.py"], "triage": "work", "refused_why": "why"})
        s = space()
        done = unittest.mock.Mock(returncode=2, stdout="validation_refused: x", stderr="")
        route = router(done)

        def run(argv, **kw):
            if argv[0] != "git":       # the slicer call itself, not git plumbing
                book.set_status("T1", "quarantined")
            return route(argv, **kw)

        with routed(run):
            slice_turn.slice_pending(book, s)
        row = book.task("T1")
        self.assertEqual("quarantined", row.get("status"))
        self.assertEqual(0, int(row.get("replans") or 0))       # slicer never spends it
        self.assertEqual(0, int(row.get("slices") or 0))        # nobody judged this card
        self.assertIn("card_moved", [line.get("kind") for line in s.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
