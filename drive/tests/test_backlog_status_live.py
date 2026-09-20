"""`is_live` is the one declared predicate for "is this card live" — never
inferred from an empty `files` list. `runs_alone` is the separate, honest
predicate for "must this card be the only one running": a live card, or a
no-files evidence card, for two different reasons. Proves both predicates,
and that seven callers (loop_judge, turn, loop_peers, replan, contract,
effort, doctor) read `is_live` rather than re-deriving it — drive-goal.py's
lane selection is the eighth, checked by grep in the same fixpoint. This
fixpoint adds three more: loop.py (`runs_alone`, the lock), loop_steps.py and
tools.py (`is_live`). test_lanes.py's own local duplicate is proved in place,
in that file, since it is not a name any other module can patch.
"""

from __future__ import annotations

import pathlib
import sys
import types
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from backlog_status import is_live
from test_loop_peers import Book

EXPECTED_TESTS = 15


class IsLiveTest(unittest.TestCase):
    def test_is_live_reads_the_declared_field(self):
        self.assertTrue(is_live({"gate_has_side_effects": True}))

    def test_is_live_never_infers_liveness_from_empty_files(self):
        # An evidence card with no files is not live unless the card says so.
        self.assertFalse(is_live({"files": []}))


class RunsAloneTest(unittest.TestCase):
    """A declared-live card and a no-files evidence card both run alone, for
    two different reasons — the live one holds the shared stack, the
    no-files one has no edit for a lane to build, so its gate runs on its own,
    one at a time. An ordinary code card does not: that is what gives
    a lane something to run."""

    def test_a_live_card_runs_alone(self):
        from backlog_status import runs_alone
        self.assertTrue(runs_alone({"gate_has_side_effects": True, "files": ["a.py"]}))

    def test_a_no_files_card_runs_alone_even_when_not_declared_live(self):
        from backlog_status import runs_alone
        self.assertTrue(runs_alone({"files": []}))

    def test_an_ordinary_code_card_does_not_run_alone(self):
        from backlog_status import runs_alone
        self.assertFalse(runs_alone({"files": ["a.py"]}))


class _LoopStub:
    """Just enough of `loop` for `_gates_on_the_branch`: a `.backlog.tasks()`."""

    def __init__(self, *rows):
        self.backlog = Book(*rows)


class CallersFollowThePredicateTest(unittest.TestCase):
    """Each caller is patched at the name IT imported, not at the definition:
    before this cartridge's fix the patch target does not exist, and that
    AttributeError is itself the proof the caller re-derived liveness instead
    of reading the shared predicate."""

    def test_loop_judge_gates_on_the_branch_follows_it(self):
        # The function moved to `loop_judge_gates` at the 200-line cap and
        # imports the predicate there; `loop_judge` still names it. Same
        # assertion, patched at the name the caller now imports.
        import loop_judge
        task = {"id": "T1", "gate": "true"}
        with unittest.mock.patch("loop_judge_gates.is_live", return_value=True):
            self.assertEqual([], loop_judge._gates_on_the_branch(_LoopStub(), task))

    def test_turn_replan_pending_follows_it(self):
        # The whole replan eligibility moved to `backlog_decision.can_replan`,
        # so `turn` no longer reads liveness itself — it reads the predicate
        # that reads it. Same assertion, patched at the name that door imports.
        import turn
        book = Book({"id": "T1", "status": "refused_contract", "replans": 0})
        calls = []
        with unittest.mock.patch("backlog_decision.is_live", return_value=True):
            out = turn.replan_pending(book, None, lambda prompt, resource=None: calls.append(prompt))
        self.assertFalse(out)
        self.assertEqual([], calls)     # a live refusal waits for a person, not a planner

    def test_loop_peers_hold_live_peers_follows_it(self):
        import loop_peers
        book = Book({"id": "T1", "status": "todo"}, {"id": "T2", "status": "todo"})
        with unittest.mock.patch("loop_peers.is_live", return_value=True):
            held = loop_peers.hold_live_peers(book, "T1", "why")
        self.assertEqual(["T2"], held)

    def test_replan_follows_it(self):
        import replan
        task = {"id": "T1", "goal": "g", "gate": "true", "files": []}
        with unittest.mock.patch("replan.is_live", return_value=True):
            out = replan.replan(None, task, lambda prompt: None)
        self.assertFalse(out.rewritten)
        self.assertIn("commander", out.why)

    def test_contract_prompt_follows_it(self):
        # `contract_prompt` moved to `contract.py` at the 200-line cap; the
        # predicate it must read is the same one.
        import contract
        task = {"id": "T1", "goal": "g", "gate": "true", "done_when": "x", "files": []}
        with unittest.mock.patch("contract.is_live", return_value=True):
            text = contract.contract_prompt(task)
        self.assertIn("helper verbs (the ONLY live commands", text)

    def test_effort_weight_follows_it(self):
        import effort
        with unittest.mock.patch("effort.is_live", return_value=True):
            self.assertEqual(2, effort.weight({}))   # nothing else here weighs anything

    def test_doctor_check_backlog_follows_it(self):
        from doctor import check_backlog
        from test_doctor import book
        from tools import helper
        live = book(gate=f"{helper()} story run-x")   # unflagged: only the patch makes this live
        with unittest.mock.patch("doctor.is_live", return_value=True):
            self.assertEqual([], [c for c in check_backlog(live) if "absolute path" in c.what])

    def test_loop_run_task_follows_it(self):
        import loop
        space = types.SimpleNamespace(root="/nonexistent")
        lp = loop.Loop(repo="", backlog=Book(), space=space, build=None, review=None)
        lp.lock.take = lambda task_id: False            # simulate: the stack is already held
        row = {"id": "T1", "gate": "true", "files": ["a.py"]}   # unflagged: only the patch says "alone"
        with unittest.mock.patch("loop.runs_alone", return_value=True):
            out = lp.run_task(row)
        self.assertEqual("waiting", out.state)

    def test_loop_steps_build_follows_it(self):
        from loop_steps import build as build_step
        from test_loop import Fakes, loop_for, task
        from worktree import Worktree
        row = task(gate="true", helper_verbs=["journal"])   # unflagged: only the patch says "live"
        lp, book, _ = loop_for(row, Fakes())
        seen = {}
        def crash(prompt, **kw):
            seen["status"] = book.task("T1")["status"]
            raise RuntimeError("stop before any live call runs")
        lp.build = crash
        tree = Worktree(lp.repo, "T1", lp.commit).create()
        with unittest.mock.patch("loop_steps.is_live", return_value=True), \
                self.assertRaises(RuntimeError):
            build_step(lp, book.task("T1"), tree, False)
        self.assertEqual("live_call_open", seen["status"])

    def test_tools_builder_tools_follows_it(self):
        from tools import builder_tools
        with unittest.mock.patch("tools.is_live", return_value=True):
            tools = builder_tools({"files": ["a.py"]})   # unflagged: only the patch says "live"
        self.assertNotIn("git", tools)   # the live builder never gets the ordinary code shell


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
