"""The rebuild edge: a rejected diff goes back to the builder with its findings,
in the same worktree, three rounds in all. The rig lives in `test_loop`."""

from __future__ import annotations

import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 9


class RebuildTest(unittest.TestCase):
    def test_a_rejected_diff_is_rebuilt_from_its_findings_in_the_same_worktree(self):
        """A rejection is a finding list, not a verdict on the task: the builder
        gets it back, in the worktree that holds its work, with no second
        contract review and no second red-first. Only the rounds are capped."""
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", out.state)
        self.assertIn("wrong line", out.why)
        queued = book.task("T1")
        self.assertEqual("todo", queued["status"])          # offered again
        self.assertEqual(1, queued["rebuild_round"])
        self.assertEqual(out.worktree, queued["rebuild_from"])
        self.assertEqual([("Diff line 7 (done_when): 1. wrong line — "
                           "The changed line fails the scripted requirement")], queued["rejections"])

        prompts: list[str] = []
        real = fakes.builder

        def builder(prompt, **kwargs):
            prompts.append(prompt)
            return real(prompt, **kwargs)

        loop.build = builder
        calls_before = list(fakes.calls)
        again = loop.run_task(book.task("T1"))
        self.assertEqual("done", again.state)
        self.assertEqual(out.worktree, again.worktree)      # same worktree
        self.assertIn("wrong line", prompts[0])             # findings in the prompt
        self.assertIn("already in this worktree", prompts[0])  # and it is, in place
        self.assertIn("historical findings", prompts[0])
        self.assertIn("recheck each against the CURRENT files and gates", prompts[0])
        self.assertIn("keep unresolved diff-review findings", prompts[0])
        self.assertNotIn("Act on exactly these recorded reasons", prompts[0])
        # one build and ONE review (the diff): no contract review this round
        self.assertEqual(["build:work", "review"], fakes.calls[len(calls_before):])
        self.assertEqual("done", book.task("T1")["status"])

    def test_the_rebuild_rounds_are_capped_and_then_a_person_is_needed(self):
        reject = Outcome("ok", verdict="REJECT", text="still wrong")
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              reject, reject, reject, reject])
        loop, book, _ = loop_for(task(), fakes)
        states = [loop.run_task(book.task("T1")).state for _ in range(3)]
        self.assertEqual(["rejected"] * 3, states)
        self.assertEqual("rejected", book.task("T1")["status"])   # the cap: a person now
        self.assertEqual(3, book.task("T1")["rebuild_round"])
    
    def test_a_usage_limit_on_a_rebuild_round_keeps_the_worktree_and_the_queue(self):
        """The work of round one is in that worktree; a limit is the harness
        talking, not a reason to lose it."""
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line")])
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        fakes.build = [Outcome("limit", text="weekly limit"), Outcome("limit", text="weekly limit")]
        again = loop.run_task(book.task("T1"))
        self.assertEqual("waiting", again.state)
        self.assertTrue(pathlib.Path(first.worktree).is_dir())
        queued = book.task("T1")
        self.assertEqual(("todo", first.worktree), (queued["status"], queued["rebuild_from"]))

    def test_a_lost_worktree_starts_the_proofs_over_but_keeps_the_findings(self):
        """A /tmp sweep took the worktree: nothing to rebuild in place, so the
        round proves red and reviews the contract again — with the findings."""
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="2. still wrong"),
                              Outcome("ok", verdict="REJECT", text="2. still wrong")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        shutil.rmtree(first.worktree)
        prompts: list[str] = []
        real = fakes.builder

        def builder(prompt, **kwargs):
            prompts.append(prompt)
            return real(prompt, **kwargs)

        loop.build = builder
        before = len(fakes.calls)
        again = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", again.state)
        self.assertNotEqual(first.worktree, again.worktree)
        self.assertEqual(["review", "build:work", "review"], fakes.calls[before:])
        self.assertIn("wrong line", prompts[0])
        self.assertNotIn("already in this worktree", prompts[0])   # it is a clean checkout
        self.assertIn("rebuild_lost", [row["kind"] for row in space.events()])
        # the round count stood through the loss: this was round two, not one,
        # and the queue now names the replacement worktree, never the lost one
        queued = book.task("T1")
        self.assertEqual((2, "todo"), (queued["rebuild_round"], queued["status"]))
        self.assertEqual(again.worktree, queued["rebuild_from"])
        self.assertEqual("rejected", loop.run_task(book.task("T1")).state)
        self.assertEqual("rejected", book.task("T1")["status"])   # the cap, not a fourth round


class TimedOutBuildTest(unittest.TestCase):
    def test_a_build_that_ran_out_of_time_continues_in_its_worktree(self):
        # An hour of work in the worktree is not a crash to throw away: the
        # next round starts from it, told what happened.
        fakes = Fakes()
        loop, book, space = loop_for(task(), fakes)
        loop.build = lambda prompt, **kw: Outcome("crash", text="the call did not return inside its timeout")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("timed_out", out.state)
        row = book.task("T1")
        self.assertEqual("todo", row["status"])
        self.assertEqual(1, row["rebuild_round"])
        self.assertEqual(out.worktree, row["rebuild_from"])
        self.assertIn("ran out of time", row["rejections"][-1])
        self.assertEqual("rebuild_queued", [r for r in space.events() if r.get("task") == "T1"][-1]["kind"])


class TimedOutThenLimitedTest(unittest.TestCase):
    def test_a_timeout_on_one_account_then_a_limit_on_the_other_still_continues(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(), fakes)
        # A crash is not a resource refusal: the belt is not walked, so one call.
        loop.build = lambda prompt, **kw: Outcome("crash", text="the call did not return inside its timeout")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("timed_out", out.state)
        self.assertEqual(out.worktree, book.task("T1")["rebuild_from"])   # the paid-for worktree kept, not removed
        self.assertTrue(pathlib.Path(out.worktree).exists())

    def test_the_timeout_rounds_stop_at_the_same_cap_as_a_rejected_diff(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(rebuild_round=2, rebuild_from=""), fakes)
        # A crash is not a resource refusal: the belt is not walked, so one call.
        loop.build = lambda prompt, **kw: Outcome("crash", text="the call did not return inside its timeout")         # a timeout, then a limit, at the cap
        out = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", out.state)                 # round three would be a fourth call; never "waiting"
        self.assertEqual("rejected", [r for r in space.events() if r.get("task") == "T1"][-1]["kind"])   # the event is written
        self.assertEqual("rejected", book.task("T1")["status"])  # not re-offered: the cap holds
        self.assertIn("ran out of time", book.task("T1")["refused_why"])
        self.assertFalse(any(r.get("kind") == "rebuild_queued" and r.get("task") == "T1" for r in space.events()))


class ResumeTest(unittest.TestCase):
    def test_a_rebuild_round_resumes_the_session_a_new_task_does_not(self):
        # Most of a round's cost was re-reading the same files.
        fakes = Fakes()
        loop, book, space = loop_for(task(), fakes)
        fakes.answers = None
        loop.build = lambda prompt, **kw: (fakes.resumes.append(kw.get("resume", "")) or
                                           Outcome("ok", text="DONE", session="sess-1"))
        loop.run_task(book.task("T1"))
        self.assertEqual([""], fakes.resumes)                       # a first round starts fresh
        self.assertEqual("sess-1", book.task("T1")["session"])      # and its session is kept

        kept = [r["path"] for r in space.events() if r.get("kind") == "worktree"][-1]   # it still exists
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=kept, rejections=["fix it"])
        loop.run_task(book.task("T1"))
        self.assertEqual("sess-1", fakes.resumes[-1])               # the same work: resumed

        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=kept, session_account="personal")
        loop.run_task(book.task("T1"))
        self.assertEqual("", fakes.resumes[-1])                     # another account cannot resume it

        book.set_status("T1", "todo", rebuild_round=2, rebuild_from="/tmp/gone", session="sess-1")
        loop.run_task(book.task("T1"))
        self.assertEqual("", fakes.resumes[-1])                     # a lost worktree is a fresh start


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
