"""A throttler that kills a turn is worse than no throttler.

Every fault is injected here at the place it would really happen — the reading
of `/proc`, the decision, the state file, the event log — and each time the
driver still gets a number it can run lanes with. The last of them is the one
that matters most: a fault the throttler could not even write down must not
become the thing that ends the turn.

It also stays completely out of the way of `--lanes N` and of a dry run: no
reading, no file, no event.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import types
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import durable
import lanes_auto
import machine_load
import throttle as throttle_mod
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from machine_load import Load, Sample
from throttle import Throttle
from workspace import Workspace

EXPECTED_TESTS = 11


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")


def args(lanes="auto", lanes_max=0, dry_run=False) -> types.SimpleNamespace:
    return types.SimpleNamespace(lanes=lanes, lanes_max=lanes_max, dry_run=dry_run)


class Angry:
    """A machine that answers every question with an exception."""

    def __call__(self) -> Sample:
        raise OSError("this machine does not want to be read")


def faults(here: Workspace) -> list[dict]:
    return [row for row in here.events() if row["kind"] == "throttle_fault"]


class FaultTest(unittest.TestCase):
    def test_a_machine_that_cannot_be_read_still_gives_the_turn_lanes(self):
        here = space()
        hand = Throttle(here, args(lanes_max=3), watch=machine_load.Watch(0.01, Angry()))
        hand.opens()
        self.assertEqual(3, hand.lanes(5))       # the ceiling, with nothing read
        hand.closes("turn-0-1", 3)
        self.assertEqual(3, hand.lanes(5))       # and again, on no evidence at all
        self.assertTrue(faults(here))

    def test_a_decision_that_raises_falls_back_to_the_last_safe_value(self):
        here = space()
        hand = Throttle(here, args(lanes_max=2))
        self.assertEqual(2, hand.lanes(5))
        with unittest.mock.patch.object(lanes_auto, "decide",
                                        side_effect=ValueError("no")):
            self.assertEqual(2, hand.lanes(5))
            self.assertEqual(1, hand.lanes(1))   # never more than there are cards
        self.assertIn("deciding", [row["what"] for row in faults(here)])

    def test_a_state_file_a_crash_cut_in_half_is_not_a_dead_driver(self):
        here = space()
        (here.root / throttle_mod.STATE).write_text('{"allow": 2, "ho', "utf-8")
        hand = Throttle(here, args())
        self.assertEqual(1, hand.lanes(5))       # fresh: no ceiling, one lane
        self.assertIn("reading its state", [row["what"] for row in faults(here)])

    def test_a_state_file_that_cannot_be_written_still_gives_a_number(self):
        here = space()
        hand = Throttle(here, args(lanes_max=3))
        with unittest.mock.patch.object(durable, "replace",
                                        side_effect=OSError("full disk")):
            self.assertEqual(3, hand.lanes(5))
        self.assertIn("keeping its state", [row["what"] for row in faults(here)])

    def test_a_log_that_cannot_be_written_is_not_the_end_of_the_turn(self):
        # The last line of defence: the recorder itself is the thing that fails.
        here = space()
        hand = Throttle(here, args(lanes_max=3))
        with unittest.mock.patch.object(Workspace, "event",
                                        side_effect=OSError("full disk")):
            self.assertEqual(3, hand.lanes(5))
            hand.closes("turn-0-1", 3)

    def test_a_watch_that_will_not_stop_still_lets_the_turn_close(self):
        here = space()
        hand = Throttle(here, args(lanes_max=3))
        hand.watch = unittest.mock.Mock()
        hand.watch.stop.side_effect = RuntimeError("the thread is gone")
        hand.closes("turn-0-1", 3)
        self.assertIn("reading what the turn cost", [row["what"] for row in faults(here)])


class QuietTest(unittest.TestCase):
    def test_lanes_n_touches_nothing_at_all(self):
        here = space()
        with unittest.mock.patch.object(machine_load, "read", Angry()):
            hand = Throttle(here, args(lanes=3))
            hand.opens()
            self.assertEqual(0, hand.lanes(5))   # 0 means "nobody chose": --lanes N stands
            hand.closes("turn-0-1", 3)
        self.assertFalse((here.root / throttle_mod.STATE).exists())
        self.assertEqual([], [row for row in here.events() if row["kind"] != "init"])

    def test_a_dry_run_decides_nothing_and_writes_nothing(self):
        here = space()
        hand = Throttle(here, args(dry_run=True))
        hand.opens()
        self.assertEqual(0, hand.lanes(5))
        hand.closes("turn-0-1", 0)
        self.assertFalse((here.root / throttle_mod.STATE).exists())


class CampaignTest(unittest.TestCase):
    def test_the_allowance_survives_a_restarted_driver(self):
        # State lives in the campaign directory, never in the vault.
        here = space()
        Throttle(here, args(lanes_max=3)).lanes(5)
        kept = json.loads((here.root / throttle_mod.STATE).read_text("utf-8"))
        self.assertEqual(3, kept["allow"])
        self.assertEqual(3, Throttle(here, args(lanes_max=3)).lanes(5))

    def test_a_ceiling_over_the_keepers_three_is_said_out_loud_and_lowered(self):
        here = space()
        self.assertEqual(3, Throttle(here, args(lanes_max=9)).lanes(9))
        said = [row for row in here.events() if row["kind"] == "lanes_ceiling_lowered"]
        self.assertEqual((9, 3), (said[-1]["asked"], said[-1]["most"]))

    def test_every_decision_is_an_event_with_its_inputs(self):
        here = space()
        hand = Throttle(here, args(lanes_max=3))
        hand.load = Load(baseline=Sample(13230344, 16903492, 0.0, 0.0, 88.88),
                         mem_avail_min_kb=10511392, swap_growth_kb=0,
                         psi_cpu_max=0.78, psi_io_max=88.88, samples=12)
        hand.lanes(5)
        row = [one for one in here.events() if one["kind"] == "lanes_decided"][-1]
        self.assertEqual((5, 3, 3, 3), (row["width"], row["lanes"], row["lanes_max"],
                                        row["most"]))
        self.assertEqual(88.88, row["baseline"]["psi_io"])
        self.assertEqual(10511392, row["signals"]["mem_avail_min_kb"])
        self.assertIn("ceiling", row["why"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
