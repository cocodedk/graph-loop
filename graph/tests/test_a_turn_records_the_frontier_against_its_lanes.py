"""Every turn writes down how wide the graph was and how many lanes it got.

The loop runs one thread per startable card up to a cap, and nothing said what
that cap cost. Now each turn records the width it was offered, the cap it
applied and the lanes it ran, and `report` names the turns where the graph
branched out further than the loop could follow.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
import unittest.mock

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE / "lib"))

from keep import Keeper
from report import as_text, report
from turn_plan import MOST_LANES, lane_cap, taking_now, width_against_lanes
from workspace import Workspace

_spec = importlib.util.spec_from_file_location("graph_goal", HERE / "graph-goal.py")
assert _spec is not None and _spec.loader is not None
graph_goal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graph_goal)

EXPECTED_TESTS = 12


def card(task_id: str, **fields) -> dict:
    return {"id": task_id, "goal": "g", "status": "todo", "needs": [],
            "files": [f"{task_id}.py"], "gate": "true", "done_when": "x", **fields}


def args(lanes: int = MOST_LANES) -> types.SimpleNamespace:
    return types.SimpleNamespace(lanes=lanes, max_tasks=0)


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="g", backlog="b.yaml")


class CapTest(unittest.TestCase):
    def test_lanes_n_still_means_a_cap_and_still_defaults_to_three(self):
        five = [card(f"T{n}") for n in range(1, 6)]
        self.assertEqual(3, lane_cap(five, args()))            # the default
        self.assertEqual(2, lane_cap(five, args(lanes=2)))     # asking for less lowers it
        self.assertEqual(1, lane_cap(five, args(lanes=0)))     # never below one
        self.assertEqual(2, len(taking_now(five, args(lanes=2))))

    def test_the_keepers_ceiling_holds_whatever_is_asked_for(self):
        five = [card(f"T{n}") for n in range(1, 6)]
        self.assertEqual(MOST_LANES, lane_cap(five, args(lanes=9)))

    def test_a_card_that_runs_alone_caps_the_turn_at_one(self):
        alone = [card("E1", files=[]), card("T2")]
        self.assertEqual(1, lane_cap(alone, args()))


class RecordTest(unittest.TestCase):
    def test_the_turn_records_width_cap_and_the_lanes_it_ran(self):
        here = space()
        ready = [card(f"T{n}") for n in range(1, 6)]
        taking = taking_now(ready, args())
        width_against_lanes(here, ready, taking, args(), "turn-0-1")
        row = [one for one in here.events() if one["kind"] == "turn_lanes"][-1]
        self.assertEqual((5, 3, 3, "turn-0-1"),
                         (row["width"], row["cap"], row["lanes"], row["turn"]))

    def test_a_live_card_beside_code_cards_is_not_counted_as_width(self):
        # The picker drops live cards from a code turn before it counts lanes;
        # a record that counted them would say the loop was narrower than the
        # graph on a turn where it ran everything it was offered.
        here = space()
        ready = [card("T1"), card("L1", gate_has_side_effects=True), card("T2")]
        taking = taking_now(ready, args())
        width_against_lanes(here, ready, taking, args(), "turn-2-1")
        row = [one for one in here.events() if one["kind"] == "turn_lanes"][-1]
        self.assertEqual((2, 3, 2), (row["width"], row["cap"], row["lanes"]))

    def test_evidence_cards_are_not_counted_as_width(self):
        # Three no-files evidence cards behind one code card: the turn can only
        # put the code card in a lane, so a width of four would report a
        # lane-cap bottleneck that does not exist.
        here = space()
        ready = [card("T1")] + [card(f"E{n}", files=[]) for n in range(1, 4)]
        taking = taking_now(ready, args())
        width_against_lanes(here, ready, taking, args(), "turn-4-1")
        row = [one for one in here.events() if one["kind"] == "turn_lanes"][-1]
        self.assertEqual((1, 3, 1), (row["width"], row["cap"], row["lanes"]))

    def test_the_cap_in_the_record_is_the_cap_the_picker_used(self):
        # One reading, not two: a record that recomputed the cap could disagree
        # with the turn it claims to describe.
        here = space()
        ready = [card("E1", files=[]), card("T2")]
        taking = taking_now(ready, args())
        width_against_lanes(here, ready, taking, args(), "turn-1-1")
        row = [one for one in here.events() if one["kind"] == "turn_lanes"][-1]
        self.assertEqual((1, 1), (row["cap"], row["lanes"]))


class ReportTest(unittest.TestCase):
    def _campaign(self) -> Workspace:
        here = space()
        for turn, (width, cap, lanes) in enumerate(
                [(2, 3, 2), (5, 3, 3), (7, 3, 3)]):
            here.event("turn_lanes", turn=f"turn-{turn}-1", width=width, cap=cap,
                       lanes=lanes)
        return here

    def test_the_report_carries_every_turn_and_names_the_wide_ones(self):
        out = report(self._campaign())
        self.assertEqual([2, 5, 7], [row["width"] for row in out["turns"]])
        self.assertEqual(["turn-1-1", "turn-2-1"], out["turns_wider"])

    def test_the_text_says_which_turns_were_wider_than_the_loop(self):
        text = as_text(report(self._campaign()))
        self.assertIn("frontier against lanes: 3 turn(s) recorded, 2 where the "
                      "graph was wider than the loop", text)
        self.assertIn("width 7  cap 3  lanes 3  — wider than the loop", text)
        self.assertIn("wider than the loop: turn-1-1, turn-2-1", text)

    def test_a_campaign_with_no_such_turn_says_nothing_about_it(self):
        out = report(space())
        self.assertEqual([], out["turns"])
        self.assertNotIn("frontier against lanes", as_text(out))


class Stop(Exception):
    """Ends the driver's loop at the one turn this test is about."""


class DriverTest(unittest.TestCase):
    """The driver itself, not the recorder called on its own."""

    def _campaign(self, dry_run: bool) -> tuple[Workspace, types.SimpleNamespace]:
        root = pathlib.Path(tempfile.mkdtemp())
        backlog = root / "b.yaml"
        backlog.write_text(yaml.safe_dump(
            {"schema": "e2e-backlog.v1", "tasks": [card(f"T{n}") for n in range(1, 6)]}))
        here = Workspace(root / "campaign").init(goal="g", backlog=str(backlog))
        (here.root / "approved").write_text("approved\n", "utf-8")
        return here, types.SimpleNamespace(
            workspace=str(here.root), dry_run=dry_run, lanes=MOST_LANES, max_tasks=0,
            idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)

    def test_the_record_is_written_before_the_lanes_start(self):
        here, args_ = self._campaign(dry_run=False)

        def lanes(*_args, **_fields):
            raise Stop

        with unittest.mock.patch.object(graph_goal, "turn_opens", lambda *a: None), \
             unittest.mock.patch.object(graph_goal, "run_lanes", lanes), \
             unittest.mock.patch.object(Keeper, "pending", lambda self: []), \
             unittest.mock.patch("publishing.behind", return_value=False), \
             self.assertRaises(Stop):
            graph_goal.command_run(args_)
        row = [one for one in here.events() if one["kind"] == "turn_lanes"][-1]
        self.assertEqual((5, 3, 3), (row["width"], row["cap"], row["lanes"]))

    def test_a_dry_run_records_nothing(self):
        here, args_ = self._campaign(dry_run=True)
        with unittest.mock.patch.object(graph_goal, "turn_opens", lambda *a: None):
            self.assertEqual(0, graph_goal.command_run(args_))
        self.assertEqual([], [one for one in here.events()
                              if one["kind"] == "turn_lanes"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
