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
import types
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import durable
import machine_load
import throttle as throttle_mod
import throttle_state
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from throttle import Throttle
from workspace import Workspace

EXPECTED_TESTS = 8


def angry(*_args, **_fields):
    raise OSError("this boundary is broken")


def _broken(where, what):
    """A patch that fails AND counts, so a boundary cannot be claimed as
    covered when nothing ever called it."""
    return unittest.mock.patch.object(where, what, side_effect=angry)


# Every place `--lanes auto` touches something outside itself, and every one of
# them is reached: `_really_reached` proves the call count rather than assuming
# it. The reader and the clock are looked up when they are CALLED — captured as
# default arguments, these two patches got zero calls and this file said more
# than it knew.
BOUNDARIES = {
    "stdout": lambda: unittest.mock.patch("builtins.print", side_effect=angry),
    "the event log": lambda: _broken(Workspace, "event"),
    "the log reader": lambda: _broken(Workspace, "events"),
    "the state file read": lambda: _broken(pathlib.Path, "read_text"),
    "the state file write": lambda: _broken(durable, "replace"),
    "/proc": lambda: _broken(machine_load, "read"),
    "the clock": lambda: _broken(machine_load, "_now"),
}
# Every method the driver calls on it.
METHODS = ("opens", "lanes", "closes", "__init__")


def space(seeded: bool = True) -> Workspace:
    """A campaign, by default with a state file already in it, so the read of
    that file is a boundary this really crosses. Made BEFORE any patch: a
    campaign that cannot be created is not what these tests are about."""
    here = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
    if seeded:
        (here.root / throttle_state.STATE).write_text('{"allow": 1}', "utf-8")
    return here


def args(lanes_max=3) -> types.SimpleNamespace:
    return types.SimpleNamespace(lanes="auto", lanes_max=lanes_max, dry_run=False)


class BoundaryTest(unittest.TestCase):
    def _turn(self, here: Workspace, broken: str, where: str) -> int:
        """One whole turn, with `where` broken during `broken` — or, when
        `broken` is "always", for every step of it."""
        made = {}

        def under(name):
            # "none" means the caller has the patch open already: opening a
            # second one over it is what made this file count zero calls.
            return (BOUNDARIES[where]() if name == broken
                    else contextlib.nullcontext())

        with under("__init__"):
            made["hand"] = Throttle(here, args(),
                                    watch=machine_load.Watch(0.01, opening=0.2))
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

    def test_every_boundary_is_really_reached(self):
        # The point of the matrix above is that these are crossed. A patch that
        # never fires proves nothing, and two of them never fired.
        for where, breaking in BOUNDARIES.items():
            here = space()                      # made before the boundary breaks
            with self.subTest(boundary=where), breaking() as spy:
                self._turn(here, "none", where)
                self.assertGreater(spy.call_count, 0, where)

    def test_nothing_is_ever_written_to_stderr(self):
        # Where a traceback would land. Nothing lands there, whatever breaks.
        deaf = unittest.mock.Mock()
        for where, breaking in BOUNDARIES.items():
            here = space()
            with unittest.mock.patch.object(sys, "stderr", deaf), breaking():
                self._turn(here, "none", where)
        self.assertEqual(0, deaf.write.call_count)

    def test_a_watch_that_cannot_be_made_does_not_escape(self):
        # It used to be built before the guard, so a machine that could not
        # make one killed the driver — with `--lanes N` as well as `auto`.
        here = space()
        with unittest.mock.patch.object(throttle_mod, "Watch", side_effect=angry):
            self.assertEqual(1, Throttle(here, args(lanes_max=1)).lanes(5))
            plain = Throttle(here, types.SimpleNamespace(
                lanes=3, lanes_max=0, dry_run=False))
        self.assertEqual(0, plain.lanes(5))

    def test_a_turn_nobody_watched_is_not_this_turns_evidence(self):
        here = space()
        hand = Throttle(here, args(), watch=machine_load.Watch(0.01, opening=0.2))
        with unittest.mock.patch.object(machine_load.Watch, "start", side_effect=angry):
            hand.opens()
        hand.closes("turn-0-1", 3)
        self.assertTrue(hand.load.broke)

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
        here = space(seeded=False)
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
