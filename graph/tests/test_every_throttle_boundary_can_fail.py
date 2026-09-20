"""Nothing the throttler touches may end a turn — and that is a CLASS, not a
list of call sites.

`--lanes auto` reaches outside itself in eight places: it prints, it writes to
the campaign log, it reads and writes its own state file, it reads `/proc`, it
reads the campaign's gate history, and it asks the clock. Each of those is made
to fail in turn against each of the throttler's public methods, and the loop
still gets a number it can run lanes with.

The failure this exists to catch was real: the line that SAID a fault had
happened printed outside the guard around it, so a broken stdout turned every
recorded fault into the thing that killed the driver.
"""

from __future__ import annotations

import contextlib
import pathlib
import sys
import tempfile
import time
import types
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import durable
import machine_load
import throttle_state
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from throttle import Throttle
from workspace import Workspace

EXPECTED_TESTS = 4


def angry(*_args, **_fields):
    raise OSError("this boundary is broken")


class Deaf:
    """A stream that refuses everything written to it."""

    def write(self, *_args):
        raise OSError("this stream is closed")

    def flush(self, *_args):
        raise OSError("this stream is closed")


# Every place `--lanes auto` touches something outside itself.
BOUNDARIES = {
    "stdout": lambda: unittest.mock.patch("builtins.print", angry),
    "stderr": lambda: unittest.mock.patch.object(sys, "stderr", Deaf()),
    "the event log": lambda: unittest.mock.patch.object(Workspace, "event", angry),
    "the log reader": lambda: unittest.mock.patch.object(Workspace, "events", angry),
    "the state file read": lambda: unittest.mock.patch.object(
        pathlib.Path, "read_text", angry),
    "the state file write": lambda: unittest.mock.patch.object(durable, "replace", angry),
    "/proc": lambda: unittest.mock.patch.object(machine_load, "read", angry),
    "the clock": lambda: unittest.mock.patch.object(time, "monotonic", angry),
}
# Every method the driver calls on it.
METHODS = ("opens", "lanes", "closes", "__init__")


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")


def args(lanes_max=3) -> types.SimpleNamespace:
    return types.SimpleNamespace(lanes="auto", lanes_max=lanes_max, dry_run=False)


class BoundaryTest(unittest.TestCase):
    def _turn(self, here: Workspace, broken: str, where: str) -> int:
        """One whole turn with `where` broken during `broken`."""
        made = {}

        def under(name):
            return BOUNDARIES[where]() if name == broken else contextlib.nullcontext()

        with under("__init__"):
            made["hand"] = Throttle(here, args(), watch=machine_load.Watch(0.01))
        hand = made["hand"]
        with under("opens"):
            hand.opens()
        with under("lanes"):
            chosen = hand.lanes(5)
        with under("closes"):
            hand.closes("turn-0-1", 3)
        return chosen

    def test_a_broken_boundary_is_never_the_end_of_a_turn(self):
        tried = 0
        for where in BOUNDARIES:
            for broken in METHODS:
                with self.subTest(boundary=where, during=broken):
                    chosen = self._turn(space(), broken, where)
                    self.assertIsInstance(chosen, int)
                    self.assertGreaterEqual(chosen, 1)
                    self.assertLessEqual(chosen, 3)
                tried += 1
        self.assertEqual(len(BOUNDARIES) * len(METHODS), tried)

    def test_the_fallback_needs_nothing_from_outside(self):
        # Everything broken at once, on a campaign whose state file is a lie:
        # the answer comes from numbers already in memory.
        here = space()
        (here.root / throttle_state.STATE).write_text('{"allow": "bad"}', "utf-8")
        with unittest.mock.patch("builtins.print", angry), \
             unittest.mock.patch.object(Workspace, "event", angry), \
             unittest.mock.patch.object(Workspace, "events", angry), \
             unittest.mock.patch.object(pathlib.Path, "read_text", angry), \
             unittest.mock.patch.object(durable, "replace", angry), \
             unittest.mock.patch.object(machine_load, "read", angry):
            hand = Throttle(here, args(lanes_max=2))
            hand.opens()
            self.assertEqual(2, hand.lanes(5))
            self.assertEqual(1, hand.lanes(1))     # never more cards than there are
            hand.closes("turn-0-1", 3)

    def test_nothing_at_all_is_touched_without_auto(self):
        here = space()
        with unittest.mock.patch.object(machine_load, "read", angry):
            hand = Throttle(here, types.SimpleNamespace(
                lanes=3, lanes_max=0, dry_run=False))
            hand.opens()
            self.assertEqual(0, hand.lanes(5))
            hand.closes("turn-0-1", 3)
        self.assertFalse((here.root / throttle_state.STATE).exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
