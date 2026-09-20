"""Reading the machine while a turn runs, and aggregating it the way the
ladder was measured: lowest MemAvailable, highest swap in use minus what was
in use at the start, highest `some avg10` of each pressure file.

The samples below are real ones, two seconds apart, from the three-lane rung.
They are what a turn hands the decision, so this is where the growth arithmetic
has to be right: swap sat flat for most of the run and then moved 1.3 GB.
"""

from __future__ import annotations

import pathlib
import sys
import threading
import time
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import machine_load
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from lanes_auto import decide
from machine_load import Sample, Watch, gather

EXPECTED_TESTS = 12

# t=0, 2, 12, 16 and 38 seconds of the three-lane rung.
RUNG = [Sample(11830676, 17323412, 0.47, 0.22, 67.80),
        Sample(10823196, 17323412, 0.56, 0.18, 67.66),
        Sample(9353396, 17323412, 2.59, 0.06, 47.49),
        Sample(5723920, 17323412, 8.26, 0.04, 40.56),
        Sample(13192892, 18666848, 2.75, 0.72, 39.24)]


LATE = Sample(1, 1)          # what the stalled reader says, far too late


def _settle(watch: Watch, seconds: float = 0.5) -> None:
    """Give the sampling thread its chance to notice, without waiting for ever
    on a flag the test may be about to prove is never set."""
    until = time.monotonic() + seconds
    while time.monotonic() < until and not watch.broke:
        time.sleep(0.01)


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


class WatchTest(unittest.TestCase):
    def test_the_baseline_is_taken_before_the_thread_starts(self):
        # The first sample must be the one with no lane running, whatever the
        # thread manages afterwards.
        taken = [Sample(9, 1), Sample(5, 3), Sample(7, 2)]
        watch = Watch(0.01, lambda: taken.pop(0) if taken else Sample(7, 2))
        watch.start()
        self.assertEqual(Sample(9, 1), watch.samples[0])
        out = watch.stop()
        self.assertEqual(Sample(9, 1), out.baseline)
        self.assertGreaterEqual(out.samples, 1)

    def test_a_reader_that_raises_reads_as_nothing_at_all(self):
        def angry() -> Sample:
            raise OSError("no /proc here")

        watch = Watch(0.01, angry)
        watch.start()                       # no exception reaches the driver
        self.assertEqual(0, watch.stop().samples)


class BrokenTest(unittest.TestCase):
    def test_a_reader_that_dies_under_load_is_not_a_clean_turn(self):
        # The baseline was read, then the machine stopped answering. Swap
        # "grew" nothing and pressure "stayed" flat because nobody looked, and
        # that must not earn another lane.
        first = [Sample(13230344, 16903492, 0.0, 0.0, 88.88)]

        def dies() -> Sample:
            if first:
                return first.pop()
            raise OSError("the machine stopped answering")

        watch = Watch(0.01, dies)
        watch.start()
        _settle(watch)
        load = watch.stop()
        self.assertTrue(load.broke)
        self.assertEqual("hold", decide(width=3, allow=1, ran=1, load=load).move)


class EmptyTest(unittest.TestCase):
    def test_a_sample_that_carries_nothing_is_not_a_reading(self):
        # A real /proc failure comes back as an EMPTY Sample, not as a raise.
        # Counted as readings, a whole baseline and two of those give a turn
        # that "moved no swap" because nobody could look.
        first = [Sample(13230344, 16903492, 0.0, 0.0, 88.88)]

        def fades() -> Sample:
            return first.pop() if first else Sample()

        watch = Watch(0.01, fades)
        watch.start()
        _settle(watch)
        load = watch.stop()
        self.assertTrue(load.broke)
        self.assertEqual("hold", decide(width=3, allow=1, ran=1, load=load).move)

    def test_a_reading_missing_half_its_numbers_is_not_one_either(self):
        self.assertFalse(Sample(13230344, None).whole)
        self.assertFalse(Sample().whole)
        self.assertTrue(Sample(13230344, 16903492).whole)      # psi stays optional


class StalledTest(unittest.TestCase):
    """A reader can stall past the end of its turn. What it finally says
    belongs to that turn, and that turn was never measured."""

    def _one_that_stalls(self):
        """A reader whose SECOND call blocks: the baseline lands, the first
        sample under load does not come back."""
        held, calls = threading.Event(), []

        def stalls() -> Sample:
            calls.append(1)
            if len(calls) == 2:
                held.wait(5)
                return LATE
            return Sample(13230344, 16903492, 0.0, 0.0, 88.88)

        return Watch(0.01, stalls), held

    def test_a_reader_that_will_not_stop_marks_the_turn_broken(self):
        watch, held = self._one_that_stalls()
        watch.start()
        time.sleep(0.1)                     # the thread is inside the blocked read
        self.assertTrue(watch.stop().broke)
        held.set()

    def test_a_late_sample_never_lands_in_the_next_turn(self):
        watch, held = self._one_that_stalls()
        watch.start()
        time.sleep(0.1)
        first = watch.stop()
        watch.start()                       # a new turn, a new buffer
        held.set()                          # and only now does the old read return
        time.sleep(0.1)
        second = watch.stop()
        self.assertTrue(first.broke)
        self.assertNotIn(LATE, watch.samples)
        self.assertGreaterEqual(second.samples, 1)


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
