"""A claim that half-landed is still the lane's to release.

`Workspace.claim` writes the claims file under its own lock and records the
`claimed` event after that lock is released. When the second step fails the
first has already happened: the card carries a live claim nobody is building.
The failure must be heard like any other lane failure. The rig is `test_lanes`'s.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_lanes import FakeLoop, book_of
from turn import run_lanes
from workspace import Workspace

EXPECTED_TESTS = 4


def breaking(space, kind_to_break: str = ""):
    """`space.event`, except that one kind of event — or every one — fails."""
    wrote = space.event

    def event(kind, **fields):
        if kind_to_break in ("", kind):
            raise OSError("the journal is unwritable")
        return wrote(kind, **fields)

    return unittest.mock.patch.object(space, "event", event)


class ClaimHalfLandedTest(unittest.TestCase):
    def test_a_lane_whose_claim_fails_halfway_releases_it_and_says_so(self):
        book = book_of("T1")
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        loop = FakeLoop()
        with breaking(space, "claimed"):        # the claims file is already written
            ran, outside = run_lanes(loop, book, space, book.tasks())
        self.assertEqual([], loop.seen)                          # never built
        self.assertEqual({}, space.running())                    # the half-claim is gone
        self.assertEqual("lane_failed", book.task("T1")["status"])
        self.assertTrue(space.alerts())                          # a person is told
        self.assertIn("failed", [row.get("kind") for row in space.events()])
        self.assertEqual(1, ran)
        self.assertFalse(outside)

    def test_a_lane_that_cannot_write_its_skip_leaves_the_decided_card_alone(self):
        # The other branch of the same error: the card was decided while the
        # turn started, so this lane never held it. Its own failure is heard —
        # but the status belongs to whoever decided the card, not to a lane
        # that only read it.
        book = book_of("T1")
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        picked = book.tasks()
        book.set_status("T1", "dropped", refused_why="decided against")
        loop = FakeLoop()
        with breaking(space, "lane_skipped"):
            run_lanes(loop, book, space, picked)
        self.assertEqual([], loop.seen)                          # never built
        self.assertEqual("dropped", book.task("T1")["status"])   # still theirs
        self.assertEqual({}, space.running())
        self.assertTrue(space.alerts())                          # and still heard


class DeadJournalTest(unittest.TestCase):
    def test_a_journal_that_never_writes_still_parks_the_card_and_tells_the_driver(self):
        # A full disk does not fail one append; it fails all of them, the
        # report of the first failure included. Every write of that report
        # stands on its own, so the card is still parked and the claim still
        # let go — and the driver hears that the record is gone, because a
        # turn nobody could record is not a turn to build the next one on.
        book = book_of("T1")
        space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
        loop = FakeLoop()
        with breaking(space), self.assertRaises(RuntimeError) as broken:
            run_lanes(loop, book, space, book.tasks())
        self.assertIn("T1", str(broken.exception))
        self.assertEqual([], loop.seen)                          # never built
        self.assertEqual("lane_failed", book.task("T1")["status"])
        self.assertEqual({}, space.running())                    # and no claim left behind
        self.assertTrue(space.alerts())                          # ALERTS.txt is written first


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
