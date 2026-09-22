"""The slicer call the plan phase makes: only on a tree task list, only one
stuck CODE card at a time, hands-off for humans' holds and LIVE cards, and the
outcome is recorded whatever it was. A BUILD turn never makes it."""

from __future__ import annotations

import contextlib
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import slice_turn
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import turn
from backlog import Backlog
from workspace import Workspace

EXPECTED_TESTS = 8


def tree_with(row: dict):
    root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
    mol = root / row["id"]
    mol.mkdir(parents=True)
    body = dict(row); body.pop("id")
    (mol / "molecule.md").write_text(cardfile.dump(body))
    return Backlog(root)


def router(slicer_result):
    """Answer git plumbing realistically; hand the slicer call its scripted
    result; remember it so assertions can read the slicer argv."""
    calls = []

    def run(argv, **kw):
        if argv[0] == "git":
            out = unittest.mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
            return out
        calls.append(argv)
        return slicer_result
    run.slicer_calls = calls
    return run


@contextlib.contextmanager
def routed(route):
    """Both doors the turn-top slice comes through: git plumbing still calls
    `subprocess.run`, the slicer itself goes through `runner.run` so it dies
    with the driver and takes its own planner calls with it."""
    def plumbing(argv, **kw):
        if argv[0] != "git":         # a paid call that skipped the runner
            raise AssertionError(f"the slicer must go through runner.run: {argv[:2]}")
        return route(argv, **kw)

    with (unittest.mock.patch("subprocess.run", side_effect=plumbing),
          unittest.mock.patch("runner.run", side_effect=route)):
        yield


def space(sources=("simulation/spec",)):
    out = Workspace(tempfile.mkdtemp()).init(goal="t", backlog="x", repo=tempfile.gettempdir())
    if sources:
        out.event("sources_declared", sources=list(sources))
    return out


class SlicePendingTest(unittest.TestCase):
    def test_a_flat_task_list_is_left_alone(self):
        import yaml  # type: ignore[import-untyped]
        flat = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
        flat.write_text(yaml.safe_dump({"tasks": [
            {"id": "T1", "status": "needs_slice", "goal": "g", "files": ["app.py"], "triage": "work", "refused_why": "the gate said why"}]}))
        with unittest.mock.patch.object(slice_turn, "subprocess", create=True) as sub:
            slice_turn.slice_pending(Backlog(flat), space())
        sub.run.assert_not_called()

    def test_a_stuck_code_card_is_handed_to_the_slicer_once(self):
        book = tree_with({"id": "T1", "status": "needs_slice", "goal": "g", "files": ["app.py"], "triage": "work", "refused_why": "the gate said why"})
        s = space()
        done = unittest.mock.Mock(returncode=0, stdout="published: T1.fix", stderr="")
        route = router(done)
        with routed(route):
            slice_turn.slice_pending(book, s)
        self.assertEqual(1, len(route.slicer_calls))
        argv = route.slicer_calls[0]
        self.assertEqual("deadbeef", argv[argv.index("--tip") + 1])
        self.assertIn("--target", argv)
        self.assertIn("T1", argv)
        finished = [e for e in s.events() if e.get("kind") == "slice_finished"]
        self.assertEqual(1, len(finished))
        self.assertEqual("published", finished[0].get("state"))

    def test_a_live_card_and_a_human_hold_are_never_the_target(self):
        s = space()
        done = unittest.mock.Mock(returncode=0, stdout="covered: unchanged", stderr="")
        for row in ({"id": "T1", "status": "needs_slice", "goal": "g", "files": ["app.py"], "refused_why": "why", "gate_has_side_effects": True},
                    {"id": "T1", "status": "needs_slice", "goal": "g", "files": ["app.py"], "refused_why": "why", "blocked_by_human": True}):
            book = tree_with(row)
            route = router(done)
            with routed(route):
                slice_turn.slice_pending(book, s)
            for argv in route.slicer_calls:      # the source-gap path may run
                self.assertNotIn("--target", argv)


class MuteWallTest(unittest.TestCase):
    def test_a_mute_needs_slice_is_not_the_slicers(self):
        # silence is never task-shape evidence (T25 was parked mute, twice)
        from backlog_status import is_wall
        mute = {"id": "T1", "status": "needs_slice", "files": ["app.py"]}
        self.assertFalse(is_wall(mute))
        speaking = dict(mute, refused_why="the gate printed this")
        self.assertFalse(is_wall(speaking))     # a reason alone is not a verdict
        verdicted = dict(mute, triage="work")
        self.assertTrue(is_wall(verdicted))

    def test_the_wall_contract_requires_a_recorded_verdict(self):
        from backlog_status import is_wall
        card = {"id": "T1", "status": "quarantined", "files": ["app.py"]}
        self.assertFalse(is_wall(card))
        self.assertTrue(is_wall(dict(card, triage="work")))


class CoveredIsNotSlicedTest(unittest.TestCase):
    def test_a_covered_answer_never_reads_as_sliced(self):
        book = tree_with({"id": "T1", "status": "done", "goal": "g", "files": ["app.py"]})
        s = space()
        done = unittest.mock.Mock(returncode=0, stdout="covered: unchanged", stderr="")
        with routed(router(done)):
            slice_turn.slice_pending(book, s)
        finished = [e for e in s.events() if e.get("kind") == "slice_finished"]
        self.assertEqual("covered", finished[0].get("state"))
        self.assertNotIn("sliced", [e.get("kind") for e in s.events()])


class ABuildTurnDoesNotPlan(unittest.TestCase):
    def test_a_turn_rewrites_one_contract_and_plans_nothing(self):
        # The two phases never mix. A turn triages, reads its flag, rewrites
        # at most one refused contract and reads the flag again; the slicer is
        # the plan phase's (`lib/plan_phase.py`) and is not reachable here.
        class Args: dry_run = False
        order = []
        class Space:
            root = tempfile.mkdtemp()      # the campaign the boundary reads from
            def stop_or_restart(self): order.append("flag"); return ""
            def code_changed(self, s): return False
        with unittest.mock.patch.object(turn, "triage_pending",
                                        side_effect=lambda *a: order.append("triage")), \
             unittest.mock.patch.object(turn, "replan_pending",
                                        side_effect=lambda *a: order.append("replan") or True) as rp:
            out = turn.turn_opens(Space(), object(), Args(), 0.0)
        self.assertIsNone(out)
        self.assertEqual(["triage", "flag", "replan", "flag"], order)
        rp.assert_called_once()

    def test_the_driver_s_turn_has_no_door_to_the_slicer(self):
        # Not a style point: the slicer used to be imported here and called at
        # the top of every turn, which is the two phases mixed by construction.
        self.assertFalse(hasattr(turn, "slice_pending"))
        self.assertFalse(hasattr(turn, "plan_now"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
