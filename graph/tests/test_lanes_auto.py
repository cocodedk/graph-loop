"""`--lanes auto`, as a table of the rungs it was measured on.

A ladder of one, two and three lanes of the same gate was run on one real
machine, sampled every two seconds. Every number below is from those runs, and
the decision is a pure function, so the table IS the test:

  1 lane   no swap moved, 10.0 GB left       -> a clean turn, earn a second
  2 lanes  414 MB of swap moved              -> hold; the machine reached for disk
  3 lanes  1.3 GB of swap moved, gates green -> halve, and hold still after it
  idle io at 94 %, 89 % under load           -> never a cut, at any level

The last line is why every judgement here is a RISE over the turn's own
baseline: an absolute io threshold would have pinned this machine to one lane
for ever.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import lanes_auto
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from lanes_auto import GB, MB, cut_reason, decide, lane_cost
from machine_load import Load, Sample

EXPECTED_TESTS = 17

# The three rungs, first sample as the baseline, aggregated as the rig did.
ONE = Load(baseline=Sample(13230344, 16903492, 0.0, 0.0, 88.88),
           mem_avail_min_kb=10511392, swap_growth_kb=0,
           psi_cpu_max=0.78, psi_mem_max=0.0, psi_io_max=88.88, samples=12)
TWO = Load(baseline=Sample(10990832, 16899060, 0.1, 0.0, 59.01),
           mem_avail_min_kb=6247788, swap_growth_kb=424356,
           psi_cpu_max=4.07, psi_mem_max=0.62, psi_io_max=59.01, samples=16)
THREE = Load(baseline=Sample(11830676, 17323412, 0.47, 0.22, 67.8),
             mem_avail_min_kb=5723920, swap_growth_kb=1343436,
             psi_cpu_max=8.26, psi_mem_max=1.08, psi_io_max=67.8, samples=20)
# The same ladder on a kernel with no pressure files: the memory half still reads.
THREE_NO_PSI = THREE._replace(baseline=Sample(11217984, 17323412),
                              swap_growth_kb=1117708, psi_cpu_max=None,
                              psi_mem_max=None, psi_io_max=None)
GATE_ALONE, GATE_AT_THREE = 22.3, 38.5      # seconds, the same gate


class RungTest(unittest.TestCase):
    def test_one_lane_moved_no_swap_and_earns_a_second(self):
        out = decide(width=3, allow=1, ran=1, load=ONE)
        self.assertEqual(("add", 2, 2), (out.move, out.lanes, out.allow))

    def test_two_lanes_moved_414_mb_of_swap_and_hold_there(self):
        out = decide(width=3, allow=2, ran=2, load=TWO)
        self.assertEqual(("hold", 2, 2), (out.move, out.lanes, out.allow))
        self.assertIn("swap moved 414 MB", out.why)
        self.assertEqual("", cut_reason(TWO))      # a hold, not a cut

    def test_three_lanes_moved_over_a_gigabyte_and_are_halved(self):
        out = decide(width=3, allow=3, ran=3, load=THREE)
        self.assertEqual(("cut", 1, 1), (out.move, out.lanes, out.allow))
        self.assertEqual(lanes_auto.HOLD_TURNS, out.hold)
        self.assertIn("swap grew 1312 MB", out.why)

    def test_the_same_rung_without_pressure_files_still_cuts(self):
        out = decide(width=3, allow=3, ran=3, load=THREE_NO_PSI)
        self.assertEqual(("cut", 1), (out.move, out.allow))

    def test_io_pressure_at_ninety_percent_is_never_a_cut(self):
        # It sat at 94 % idle and fell to 89 % under one lane. Even a 39-point
        # RISE is not a cut: io is recorded and never acted on.
        self.assertEqual("", cut_reason(ONE))
        loud = ONE._replace(baseline=Sample(13230344, 16903492, 0.0, 0.0, 60.0),
                            psi_io_max=99.0)
        self.assertEqual("", cut_reason(loud))
        self.assertEqual("add", decide(width=3, allow=1, ran=1, load=loud).move)

    def test_one_lanes_cost_is_the_first_turns_drop(self):
        self.assertEqual(2718952, lane_cost(ONE, 1))
        self.assertIsNone(lane_cost(None, 1))
        self.assertIsNone(lane_cost(ONE, 0))


class CutTest(unittest.TestCase):
    def test_memory_or_cpu_pressure_over_twenty_points_cuts(self):
        heavy = THREE._replace(swap_growth_kb=0, psi_mem_max=24.0)
        self.assertIn("memory pressure rose 24 points", cut_reason(heavy))
        busy = THREE._replace(swap_growth_kb=0, psi_cpu_max=30.0)
        self.assertIn("cpu pressure rose 30 points", cut_reason(busy))
        gentle = THREE._replace(swap_growth_kb=0, psi_mem_max=19.0)
        self.assertEqual("", cut_reason(gentle))

    def test_a_gate_far_slower_than_its_time_alone_cuts(self):
        measured = GATE_AT_THREE / GATE_ALONE               # 1.7 on the ladder
        self.assertEqual("", cut_reason(ONE, measured))
        self.assertIn("2.6 times its time alone", cut_reason(ONE, 2.6))

    def test_a_cut_holds_still_for_two_turns_before_it_climbs(self):
        first = decide(width=3, allow=3, ran=3, load=THREE)
        second = decide(width=3, allow=first.allow, ran=1, hold=first.hold, load=ONE)
        self.assertEqual(("hold", 1, 1), (second.move, second.lanes, second.hold))
        third = decide(width=3, allow=second.allow, ran=1, hold=second.hold, load=ONE)
        self.assertEqual(("hold", 0), (third.move, third.hold))
        fourth = decide(width=3, allow=third.allow, ran=1, hold=third.hold, load=ONE)
        self.assertEqual("add", fourth.move)


class CeilingTest(unittest.TestCase):
    def test_a_ceiling_starts_at_the_ceiling_not_at_one(self):
        out = decide(width=5, ceiling=3, allow=0)
        self.assertEqual(("start", 3, 3), (out.move, out.lanes, out.allow))
        self.assertEqual(2, decide(width=2, ceiling=3, allow=0).lanes)   # min(width, N)

    def test_without_a_ceiling_it_starts_at_one(self):
        out = decide(width=5)
        self.assertEqual(("start", 1, 1), (out.move, out.lanes, out.allow))
        self.assertIn("one lane", out.why)

    def test_the_keepers_three_holds_over_any_ceiling(self):
        self.assertEqual(3, decide(width=9, ceiling=9, allow=0).lanes)
        self.assertEqual(3, decide(width=9, ceiling=9, allow=3, ran=3, load=ONE).lanes)

    def test_lanes_never_pass_the_cards_there_are(self):
        out = decide(width=1, ceiling=3, allow=3, ran=3, load=ONE)
        self.assertEqual((1, 3), (out.lanes, out.allow))   # the allowance is kept


class ThinTest(unittest.TestCase):
    def test_no_lane_is_added_while_the_reserve_is_thin(self):
        thin = ONE._replace(mem_avail_min_kb=lanes_auto.RESERVE_KB + 2 * GB)
        out = decide(width=3, allow=1, ran=1, load=thin, lane_cost_kb=2.6 * GB)
        self.assertEqual("hold", out.move)
        self.assertIn("reserve", out.why)

    def test_a_machine_that_says_nothing_never_adds_a_lane(self):
        for load in (None, Load(), Load(baseline=Sample(), samples=3)):
            out = decide(width=3, allow=1, ran=1, load=load)
            self.assertEqual(("hold", 1), (out.move, out.lanes), load)

    def test_a_turn_that_did_not_use_its_allowance_teaches_nothing(self):
        out = decide(width=3, allow=2, ran=1, load=ONE)
        self.assertEqual(("hold", 2), (out.move, out.allow))
        self.assertIn("1 of 2 lanes ran", out.why)


class UnitTest(unittest.TestCase):
    def test_the_thresholds_are_the_measured_ones(self):
        self.assertEqual((500 * MB, 2.5), (lanes_auto.SWAP_CUT_KB, lanes_auto.GATE_CUT))
        self.assertEqual((20.0, 3 * GB), (lanes_auto.PRESSURE_CUT, lanes_auto.RESERVE_KB))
        self.assertEqual(2.5 * GB, lanes_auto.LANE_COST_KB)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
