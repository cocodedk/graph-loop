"""Watching one turn: what counts as a reading, and what a turn has to prove.

The law is `machine_load.fresh` — no fresh evidence, no increase — and this is
where it is put under load. A reader that dies, one that returns nothing, one
that stalls past the end of its turn, a start that cannot happen at all: each
of them ends in HOLD, and none of them ends in a raise.
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
from machine_load import Load, Sample, Watch

EXPECTED_TESTS = 11

LATE = Sample(1, 1)          # what the stalled reader says, far too late


def _settle(watch: Watch, seconds: float = 0.5) -> None:
    """Give the sampling thread its chance to notice, without waiting for ever
    on a flag the test may be about to prove is never set."""
    until = time.monotonic() + seconds
    while time.monotonic() < until and not watch.broke:
        time.sleep(0.01)


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


class LawTest(unittest.TestCase):
    """No fresh evidence, no increase — one law, one home."""

    WHOLE = Load(baseline=Sample(13230344, 16903492), mem_avail_min_kb=10511392,
                 swap_growth_kb=0, samples=2)

    def test_a_reader_that_never_returns_does_not_hang_the_driver(self):
        held = threading.Event()
        watch = Watch(0.01, lambda: held.wait(30) or Sample(1, 1), opening=0.2)
        began = time.monotonic()
        watch.start()                       # bounded: it does not wait 30 seconds
        self.assertLess(time.monotonic() - began, 5)
        self.assertFalse(machine_load.fresh(watch.stop()))
        held.set()

    def test_a_start_that_fails_leaves_no_evidence_behind(self):
        watch = Watch(0.01, lambda: Sample(13230344, 16903492))
        watch.start()
        _settle(watch, 0.1)
        self.assertTrue(machine_load.fresh(watch.stop()))    # a real turn
        with unittest.mock.patch.object(threading, "Thread", side_effect=OSError("no")), \
             self.assertRaises(OSError):
            watch.start()                   # and now one that cannot begin
        self.assertFalse(machine_load.fresh(watch.stop()))
        self.assertEqual(0, watch.stop().samples)

    def test_a_reader_that_exits_the_thread_is_not_an_increase(self):
        taken = []

        def quits() -> Sample:
            taken.append(1)
            if len(taken) > 2:
                raise SystemExit(0)
            return Sample(13230344, 16903492)

        watch = Watch(0.01, quits)
        watch.start()
        _settle(watch)
        self.assertFalse(machine_load.fresh(watch.stop()))

    def test_what_the_law_asks_of_a_reading(self):
        self.assertTrue(machine_load.fresh(self.WHOLE))
        self.assertFalse(machine_load.fresh(None))
        self.assertFalse(machine_load.fresh(self.WHOLE._replace(broke=True)))
        self.assertFalse(machine_load.fresh(self.WHOLE._replace(carried=True)))
        self.assertFalse(machine_load.fresh(self.WHOLE._replace(samples=1)))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
