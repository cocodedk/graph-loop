"""Reading the machine while a turn runs, and aggregating it the way the
ladder was measured: lowest MemAvailable, highest swap in use minus what was
in use at the start, highest `some avg10` of each pressure file.

The samples below are real ones, two seconds apart, from the three-lane rung.
They are what a turn hands the decision, so this is where the growth arithmetic
has to be right: swap sat flat for most of the run and then moved 1.3 GB.
What a turn has to PROVE before any of it counts is
`test_a_turn_must_earn_its_readings`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import machine_load
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from machine_load import Sample, Watch, gather

EXPECTED_TESTS = 6

# t=0, 2, 12, 16 and 38 seconds of the three-lane rung.
RUNG = [Sample(11830676, 17323412, 0.47, 0.22, 67.80),
        Sample(10823196, 17323412, 0.56, 0.18, 67.66),
        Sample(9353396, 17323412, 2.59, 0.06, 47.49),
        Sample(5723920, 17323412, 8.26, 0.04, 40.56),
        Sample(13192892, 18666848, 2.75, 0.72, 39.24)]


class GatherTest(unittest.TestCase):
    def test_the_aggregate_is_the_one_the_rungs_were_read_with(self):
        out = gather(RUNG)
        self.assertEqual(5723920, out.mem_avail_min_kb)
        self.assertEqual(1343436, out.swap_growth_kb)       # 18666848 - 17323412
        self.assertEqual((8.26, 0.72, 67.80),
                         (out.psi_cpu_max, out.psi_mem_max, out.psi_io_max))
        self.assertEqual(RUNG[0], out.baseline)             # the turn's own baseline
        self.assertEqual(5, out.samples)

    def test_growth_is_measured_from_the_start_of_the_turn(self):
        # Swap already in use from yesterday is not this turn's doing: 16 GB
        # standing and none of it added reads as no growth at all.
        flat = [Sample(swap_used_kb=16903492) for _ in range(4)]
        self.assertEqual(0, gather(flat).swap_growth_kb)

    def test_a_machine_without_pressure_files_says_nothing_rather_than_zero(self):
        out = gather([Sample(11217984, 17323412), Sample(5804816, 18441120)])
        self.assertEqual(1117708, out.swap_growth_kb)
        self.assertEqual((None, None, None),
                         (out.psi_cpu_max, out.psi_mem_max, out.psi_io_max))

    def test_nothing_read_is_nothing_claimed(self):
        out = gather([])
        self.assertEqual((None, None, 0),
                         (out.mem_avail_min_kb, out.swap_growth_kb, out.samples))


class ClockTest(unittest.TestCase):
    def test_a_turn_is_timed_by_the_one_clock(self):
        watch = Watch(0.01, lambda: Sample(13230344, 16903492))
        with unittest.mock.patch.object(machine_load, "_now",
                                        side_effect=[10.0, 12.5]) as clock:
            watch.start()
            self.assertEqual(2.5, watch.stop().seconds)
        self.assertEqual(2, clock.call_count)


class ReadTest(unittest.TestCase):
    def test_a_missing_pressure_file_reads_as_nothing(self):
        with unittest.mock.patch("builtins.open", side_effect=OSError("no such file")):
            self.assertIsNone(machine_load.pressure("cpu"))
            self.assertEqual({}, machine_load.meminfo())
            self.assertEqual(Sample(), machine_load.read())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
