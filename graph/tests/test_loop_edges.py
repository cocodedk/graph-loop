"""The loop's edges: accounts, holds, broken reviews, side effects, claims,
gate ownership and a builder that stops. The rig lives in `test_loop`."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 13


class AccountTest(unittest.TestCase):
    def test_a_usage_limit_switches_account_and_costs_no_attempt(self):
        fakes = Fakes(build=[Outcome("limit", text="You've hit your weekly limit"),
                             Outcome("ok", text="done")])
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(["review", "build:work", "build:second", "review"],
                         fakes.calls)
        self.assertEqual(1, space.attempts("T1"))

    def test_both_accounts_limited_leaves_the_task_for_later(self):
        fakes = Fakes(build=[Outcome("limit", text="limit"), Outcome("limit", text="limit")])
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("waiting", out.state)
        self.assertEqual(0, space.attempts("T1"))
        self.assertEqual("todo", book.task("T1")["status"])

    def test_a_permission_denial_is_a_harness_fault_and_not_an_attempt(self):
        fakes = Fakes(build=[Outcome("harness", text="Edit denied")])
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("harness", out.state)
        self.assertEqual(0, space.attempts("T1"))
        # the call was paid for: the card continues in the SAME tree, counted,
        # never a fresh tree that re-pays the build
        row = book.task("T1")
        self.assertEqual(("todo", 1, out.worktree),
                         (row["status"], row["rebuild_round"], row["rebuild_from"]))


class HoldTest(unittest.TestCase):
    def test_a_task_held_for_a_human_is_never_started(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(blocked_by_human=True), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("held", out.state)
        self.assertEqual([], fakes.calls)

    def test_a_live_task_takes_the_lock_and_a_second_one_waits(self):
        # The lock is the STACK's, one file for the whole host that no
        # environment moves: this stands in for where it lives, or the test
        # takes the lock a driver running on this host is holding.
        self.enterContext(unittest.mock.patch("worktree_lock.shared",
                                              return_value=tempfile.mkdtemp()))
        fakes = Fakes()
        loop, book, _ = loop_for(task(files=[], gate="grep -q two a.py"), fakes)
        loop.lock.take("someone-else")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("waiting", out.state)
        self.assertIn("someone-else", out.why)


class SideEffectTest(unittest.TestCase):
    def test_a_gate_that_performs_the_work_is_not_run_before_the_builder(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(gate="true", gate_has_side_effects=True), fakes)
        out = loop.run_task(book.task("T1"))
        # The gate is green from the start, which would normally refuse the task;
        # with side effects declared it is never run before the work.
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(1, len([r for r in space.events()
                                 if r["kind"] == "skipped_red_first"]))


class WorktreeClaimTest(unittest.TestCase):
    def test_the_claim_carries_the_real_worktree_once_it_is_cut(self):
        # The first version passed the claim row back into claim() whole, and the
        # `since` field crashed the driver twice before the supervisor's guard.
        import os
        fakes = Fakes()
        loop, book, space = loop_for(task(), fakes)
        space.claim("T1", pgid=os.getpgid(0), account="lane", worktree="")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)


class GateOwnershipTest(unittest.TestCase):
    def test_a_builder_may_not_edit_the_file_its_gate_runs(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(files=["test_thing.py"],
                                      gate="python3 -m unittest test_thing"), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("refused", out.state)
        self.assertIn("may edit the test its own gate runs", out.why)
        self.assertEqual([], fakes.calls)

    def test_unless_writing_that_test_is_the_work_itself(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(files=["test_thing.py"],
                                      gate="python3 -m unittest test_thing",
                                      gate_files_are_the_work=True), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertNotEqual("refused", out.state)

    def test_a_gate_that_exercises_the_file_being_changed_is_fine(self):
        # `import a; a.greet()` is behaviour, not a test the builder can gut.
        fakes = Fakes()
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)


class BlockedTest(unittest.TestCase):
    def test_an_unclear_answer_still_faces_the_gate_and_raises_an_alert(self):
        # The gate is the judge; an answer nobody can read is a thing to tell a
        # person about, not a reason to throw away work that passes.
        fakes = Fakes(build=[Outcome("ok", text="I think that is everything?")])
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(1, len(space.alerts()))

    def test_a_builder_that_says_blocked_is_believed_and_a_person_is_told(self):
        blocked = ('{"result": "BLOCKED", "blocked": true, "needs_person": true, '
                   '"why": "the fix needs a new verb"}')
        from distress import INSTRUCTION, TEMPLATE
        fakes = Fakes(build=[Outcome("ok", text=blocked)], edit=None)
        loop, book, space = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("blocked", out.state)
        self.assertEqual("blocked_by_agent", book.task("T1")["status"])
        self.assertTrue(book.task("T1")["blocked_by_human"])
        self.assertFalse(book.startable())
        self.assertIn(INSTRUCTION + TEMPLATE, fakes.prompts[0])
        self.assertEqual("blocked_by_agent", book.task("T1")["status"])
        self.assertEqual(1, len([r for r in space.events()
                                 if r["kind"] == "needs_a_person"]))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
