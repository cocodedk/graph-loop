"""One rule, at the edge of the throttle, in place of a rule per path.

Any fault at all — making the thing, reading its state, measuring, stopping the
watch, deciding, recording, persisting, printing — makes the next lane count
ONE and the turn it happened in not fresh, so the turn after it cannot earn an
increase from it either. There is nothing to work out and nothing to know: a
throttler that is not sure runs one lane.

It replaced "hold at the current count", which needed a current count that was
reliably known, and grew a new way to be wrong every time something else could
fail. `--lanes N` is untouched by all of it, and never raises either.
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
import machine_load
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from machine_load import Load, Sample, Watch
from throttle import Throttle
from workspace import Workspace

EXPECTED_TESTS = 7

# One lane on the rung that moved no swap and left 10 GB: a clean turn.
LIGHT = Load(baseline=Sample(13230344, 16903492, 0.0, 0.0, 88.88),
             mem_avail_min_kb=10511392, swap_growth_kb=0, psi_cpu_max=0.78,
             psi_mem_max=0.0, psi_io_max=88.88, samples=12)
# Three lanes on the rung that moved 1.3 GB of swap.
HEAVY = LIGHT._replace(swap_growth_kb=1343436, mem_avail_min_kb=5723920, samples=20)
FULL = OSError(28, "No space left on device")


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")


def args(lanes_max: int = 0) -> types.SimpleNamespace:
    return types.SimpleNamespace(lanes="auto", lanes_max=lanes_max, dry_run=False)


def driver(here: Workspace, lanes_max: int = 0, load: Load | None = None) -> Throttle:
    hand = Throttle(here, args(lanes_max))
    if load is not None:
        hand.watch = unittest.mock.Mock()
        hand.watch.stop.return_value = load
    return hand


class FaultTest(unittest.TestCase):
    def test_a_state_file_nobody_can_read_opens_at_one_not_at_the_ceiling(self):
        here = space()
        hand = driver(here, 3, HEAVY)
        self.assertEqual(3, hand.lanes(5))          # it opens at the ceiling
        hand.opens()
        hand.closes("turn-0-1", 3)
        self.assertEqual(1, hand.lanes(5))          # 1.3 GB of swap: halved, kept
        with unittest.mock.patch.object(pathlib.Path, "read_text", side_effect=FULL):
            restarted = driver(here, 3)
        self.assertEqual(1, restarted.lanes(5))

    def test_an_opening_that_could_not_be_written_never_becomes_three(self):
        here = space()
        hand = driver(here, 3, HEAVY)
        with unittest.mock.patch.object(durable, "replace", side_effect=FULL):
            self.assertEqual(1, hand.lanes(5))      # the opening is not granted
        hand.opens()
        hand.closes("turn-0-1", 1)                  # and the machine moves 1.3 GB
        self.assertEqual(1, hand.lanes(5))

    def test_a_clock_that_fails_while_the_turn_is_stopping(self):
        here = space()
        hand = driver(here, 3)
        hand.watch = Watch(0.01, lambda: Sample(13230344, 16903492), opening=0.2)
        self.assertEqual(3, hand.lanes(5))
        hand.opens()
        with unittest.mock.patch.object(machine_load, "_now", side_effect=FULL):
            hand.closes("turn-0-1", 3)
        self.assertEqual(1, hand.lanes(5))

    def test_a_turn_whose_writes_all_failed_earns_nothing(self):
        here = space()
        hand = driver(here, 0, LIGHT)
        self.assertEqual(1, hand.lanes(3))
        hand.opens()
        with unittest.mock.patch.object(durable, "replace", side_effect=FULL):
            hand.closes("turn-0-1", 1)
        self.assertEqual(1, hand.lanes(3))

    def test_a_broken_pipe_on_the_last_line_keeps_the_increase_off(self):
        here = space()
        hand = driver(here, 0, LIGHT)
        self.assertEqual(1, hand.lanes(3))
        hand.opens()
        hand.closes("turn-0-1", 1)                  # a clean turn: it would rise
        with unittest.mock.patch("builtins.print", side_effect=BrokenPipeError()):
            self.assertEqual(1, hand.lanes(3))
        self.assertEqual(1, hand.allow)

    def test_a_clean_run_of_it_still_climbs(self):
        # The control: every one of these would pass on a throttler stuck at one.
        here = space()
        hand = driver(here, 0, LIGHT)
        self.assertEqual(1, hand.lanes(3))
        hand.opens()
        hand.closes("turn-0-1", 1)
        self.assertEqual(2, hand.lanes(3))

    def test_lanes_n_is_untouched_by_any_of_it(self):
        here = space()
        with unittest.mock.patch.object(durable, "replace", side_effect=FULL), \
             unittest.mock.patch("builtins.print", side_effect=BrokenPipeError()), \
             unittest.mock.patch.object(pathlib.Path, "read_text", side_effect=FULL):
            plain = Throttle(here, types.SimpleNamespace(
                lanes=3, lanes_max=0, dry_run=False))
            plain.opens()
            self.assertEqual(0, plain.lanes(5))     # nobody chose: --lanes N stands
            plain.closes("turn-0-1", 3)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
