"""A gate's wall time is a throttle signal only against the SAME gate run alone.

Two cards' gates are two different programs, so one card's 40 seconds says
nothing about another's 20. A turn that ran a single lane is what teaches a
card's lone time; a turn with several lanes is what is then measured against
it. The ladder this was built from: the same gate took 22.3 seconds alone,
30.4 with two lanes and 36.5–38.5 with three — 1.7 times, well under the 2.5
that cuts.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import types
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from lanes_auto import GATE_CUT, cut_reason
from throttle import Throttle
from workspace import Workspace

EXPECTED_TESTS = 4
ALONE, AT_THREE, SLOW = 22.3, 38.5, 60.0


def hand() -> Throttle:
    here = Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")
    return Throttle(here, types.SimpleNamespace(lanes="auto", lanes_max=3,
                                                dry_run=False))


def gate(throttle: Throttle, turn: str, task: str, seconds: float) -> None:
    throttle.space.event("step", task=task, step="gate", seconds=seconds, turn=turn)


class RatioTest(unittest.TestCase):
    def test_a_single_lane_turn_teaches_that_cards_lone_time(self):
        one = hand()
        gate(one, "turn-0-1", "T1", ALONE)
        self.assertIsNone(one._gate_ratio("turn-0-1", 1))
        self.assertEqual({"T1": ALONE}, one.state["gate_alone"])

    def test_a_busy_turn_is_measured_against_that_same_card(self):
        one = hand()
        gate(one, "turn-0-1", "T1", ALONE)
        one._gate_ratio("turn-0-1", 1)
        gate(one, "turn-1-1", "T1", AT_THREE)
        self.assertAlmostEqual(AT_THREE / ALONE, one._gate_ratio("turn-1-1", 3))
        self.assertEqual("", cut_reason(None, AT_THREE / ALONE))     # 1.7: no cut
        self.assertIn("times its time alone", cut_reason(None, SLOW / ALONE))

    def test_a_card_never_seen_alone_is_not_compared_with_another(self):
        one = hand()
        gate(one, "turn-0-1", "T1", ALONE)
        one._gate_ratio("turn-0-1", 1)
        gate(one, "turn-1-1", "T2", SLOW)          # a different gate entirely
        self.assertIsNone(one._gate_ratio("turn-1-1", 3))

    def test_only_this_turn_s_gates_are_read(self):
        one = hand()
        gate(one, "turn-0-1", "T1", ALONE)
        one._gate_ratio("turn-0-1", 1)
        gate(one, "turn-1-1", "T1", ALONE * GATE_CUT * 2)
        self.assertIsNone(one._gate_ratio("turn-2-1", 3))   # a turn that ran no gate


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
