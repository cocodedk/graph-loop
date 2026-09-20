"""The driver is killed and restarted routinely: on new code, by the
supervisor, by a person. Everything `--lanes auto` learned has to survive that
or be safely re-derived, and a state file with anything at all in it has to
degrade to a safe number rather than kill the driver it is read by.
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
import lanes_auto
import throttle_state
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from machine_load import Load, Sample
from throttle import Throttle
from workspace import Workspace

EXPECTED_TESTS = 8

# The three-lane rung: 1.3 GB of swap moved inside the turn.
HEAVY = Load(baseline=Sample(11830676, 17323412, 0.47, 0.22, 67.8),
             mem_avail_min_kb=5723920, swap_growth_kb=1343436,
             psi_cpu_max=8.26, psi_mem_max=1.08, psi_io_max=67.8, samples=20)


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")


def args(lanes_max=0) -> types.SimpleNamespace:
    return types.SimpleNamespace(lanes="auto", lanes_max=lanes_max, dry_run=False)


def driver(here: Workspace, lanes_max: int = 3, load: Load | None = None) -> Throttle:
    """A fresh driver over the same campaign directory."""
    hand = Throttle(here, args(lanes_max))
    if load is not None:
        hand.watch = unittest.mock.Mock()
        hand.watch.stop.return_value = load
    return hand


class CorruptTest(unittest.TestCase):
    def test_a_state_file_of_nonsense_gives_a_number_not_a_traceback(self):
        here = space()
        (here.root / throttle_state.STATE).write_text(
            '{"allow": "bad", "hold": "worse", "gate_alone": "none"}', "utf-8")
        self.assertEqual(2, driver(here, lanes_max=2).lanes(5))

    def test_a_state_file_holding_a_list_is_read_as_no_state_at_all(self):
        here = space()
        (here.root / throttle_state.STATE).write_text("[1, 2, 3]", "utf-8")
        self.assertEqual(1, driver(here, lanes_max=0).lanes(5))

    def test_a_nonsense_reading_in_the_file_is_dropped_not_acted_on(self):
        self.assertIsNone(throttle_state.load_of({"swap_growth_kb": "lots"})
                          .swap_growth_kb)
        self.assertIsNone(throttle_state.load_of({}))
        self.assertIsNone(throttle_state.load_of("not a reading"))


class CeilingTest(unittest.TestCase):
    def test_the_fallback_obeys_a_ceiling_lowered_since(self):
        # The allowance of three is in the file; the owner restarts with one.
        here = space()
        driver(here, lanes_max=3).lanes(5)
        hand = driver(here, lanes_max=1)
        with unittest.mock.patch.object(lanes_auto, "decide",
                                        side_effect=ValueError("no")):
            self.assertEqual(1, hand.lanes(5))


class CarriedTest(unittest.TestCase):
    def _a_heavy_turn(self, here: Workspace) -> Throttle:
        """One turn at three lanes that moves 1.3 GB of swap, and stops there
        — where a driver is killed: after the turn, before the next decision."""
        first = driver(here, load=HEAVY)
        self.assertEqual(3, first.lanes(5))          # starts at the ceiling
        first.opens()
        first.closes("turn-0-1", 3)
        return first

    def test_the_driver_that_ran_the_turn_halves_on_it(self):
        first = self._a_heavy_turn(space())
        self.assertEqual(1, first.lanes(5))

    def test_and_so_does_the_one_that_restarts_in_its_place(self):
        # The reading is the only reason to cut, and it was made by a process
        # that is gone. Without it the new driver runs three lanes again.
        here = space()
        self._a_heavy_turn(here)
        self.assertEqual(1, driver(here).lanes(5))

    def test_the_reading_itself_is_what_is_carried(self):
        here = space()
        hand = driver(here, load=HEAVY)
        hand.lanes(5)
        hand.opens()
        hand.closes("turn-0-1", 3)
        kept = throttle_state.read(here.root / throttle_state.STATE)
        self.assertEqual(1343436, kept["load"]["swap_growth_kb"])
        self.assertEqual(HEAVY, throttle_state.load_of(kept["load"]))

    def test_a_campaign_that_never_ran_a_turn_carries_nothing(self):
        here = space()
        self.assertEqual(throttle_state.FRESH,
                         throttle_state.read(here.root / throttle_state.STATE))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
