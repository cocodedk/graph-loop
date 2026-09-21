"""A raised lane count is granted only when every step of granting it worked.

Holding is free: it needs no disk, no log and no history. Raising is not — the
number has to be written down before the next driver runs on it, and the turn
it rests on has to have been read in full. So an increase is the LAST thing
that happens, after everything that can fail has not, and a failure anywhere in
that path leaves the count where it was and says so once.

Cuts are the other way round: they take effect at once, whatever fails
afterwards. Doubt always resolves downward.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import types
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import durable
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from machine_load import Load, Sample
from throttle import Throttle
from workspace import Workspace

EXPECTED_TESTS = 6

# One lane, on the rung that moved no swap and left 10 GB: a clean turn.
LIGHT = Load(baseline=Sample(13230344, 16903492, 0.0, 0.0, 88.88),
             mem_avail_min_kb=10511392, swap_growth_kb=0, psi_cpu_max=0.78,
             psi_mem_max=0.0, psi_io_max=88.88, samples=12)
FULL = OSError(28, "No space left on device")
SHUT = PermissionError(13, "Permission denied")


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")


def driver(here: Workspace) -> Throttle:
    """A throttler with no ceiling, so it starts at one lane and climbs."""
    hand = Throttle(here, types.SimpleNamespace(lanes="auto", lanes_max=0,
                                                dry_run=False))
    hand.watch = unittest.mock.Mock()
    hand.watch.stop.return_value = LIGHT
    return hand


class IncreaseTest(unittest.TestCase):
    def _after_a_clean_turn(self, here: Workspace) -> Throttle:
        hand = driver(here)
        self.assertEqual(1, hand.lanes(3))      # no ceiling: it starts at one
        hand.opens()
        hand.closes("turn-0-1", 1)
        return hand

    def test_a_clean_turn_everything_agreed_on_does_raise_the_count(self):
        # The control. Without it the two below would pass on a throttler that
        # never climbs at all.
        self.assertEqual(2, self._after_a_clean_turn(space()).lanes(3))

    def test_a_full_disk_holds_the_count_where_it_was(self):
        hand = self._after_a_clean_turn(space())
        with unittest.mock.patch.object(durable, "replace", side_effect=FULL):
            self.assertEqual(1, hand.lanes(3))
        self.assertEqual(1, hand.allow)         # and nothing adopted it either

    def test_a_disk_that_comes_back_lets_a_later_turn_raise_it(self):
        # A fault leaves the throttle knowing nothing, so the turn it happened
        # in is not evidence either. One whole turn later it climbs again.
        here = space()
        hand = self._after_a_clean_turn(here)
        with unittest.mock.patch.object(durable, "replace", side_effect=FULL):
            self.assertEqual(1, hand.lanes(3))
        self.assertEqual(1, hand.lanes(3))
        hand.opens()
        hand.closes("turn-1-1", 1)              # a whole turn, nothing wrong
        self.assertEqual(2, hand.lanes(3))

    def test_a_gate_history_nobody_can_read_holds_it_too(self):
        here = space()
        hand = driver(here)
        self.assertEqual(1, hand.lanes(3))
        hand.opens()
        with unittest.mock.patch.object(Workspace, "events", side_effect=SHUT):
            hand.closes("turn-0-1", 1)
        # Part of this turn could not be read, so the turn is not evidence for
        # another lane — the same law a dead reader answers to.
        self.assertEqual(1, hand.lanes(3))
        self.assertTrue(hand.load.broke)

    def test_a_failure_in_that_path_is_said_once(self):
        hand = self._after_a_clean_turn(space())
        with unittest.mock.patch.object(durable, "replace", side_effect=FULL):
            hand.lanes(3)
        said = [row["what"] for row in hand.space.events()
                if row["kind"] == "throttle_fault"]
        self.assertEqual(1, len(said), said)
        self.assertIn("deciding this turn's lanes", said)

    def test_a_cut_still_lands_when_the_disk_is_full(self):
        # The other direction: a cut is not held up by anything.
        here = space()
        hand = driver(here)
        hand.lanes(3)
        hand.watch.stop.return_value = LIGHT._replace(swap_growth_kb=1343436)
        hand.opens()
        hand.closes("turn-0-1", 1)
        with unittest.mock.patch.object(durable, "replace", side_effect=FULL):
            self.assertEqual(1, hand.lanes(3))
        self.assertEqual(1, hand.allow)         # the cut landed, disk or no disk


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
