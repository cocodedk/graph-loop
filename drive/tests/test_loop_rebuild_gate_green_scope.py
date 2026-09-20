"""The gate itself can leave its lane on the run that decides its colour --
an in-place round finding it green, or an ordinary fresh round proving it red
as expected -- by moving HEAD, or writing outside the task's files, not only
on judge()'s later rerun of the same gate. Mirrors test_loop_rebuild_gate_
green's setup; the rig lives in test_loop."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import loop_judge
from providers import Outcome
from test_loop import Fakes, loop_for, task
from worktree import HeadMoved, Worktree

EXPECTED_TESTS = 5


class GateLeftItsLaneTest(unittest.TestCase):
    def test_a_first_run_mutation_ends_the_round_without_a_second_gate_run(self):
        # This round's gate writes outside.txt on its very FIRST run -- the
        # one red_first uses to find it already green. Before that run was
        # checked on the spot, the ending was still right (judge's own guard
        # caught the same outside.txt) but only after running the gate a
        # SECOND time for no reason: wasteful for an idempotent gate, wrong
        # for one that is not.
        runs = str(pathlib.Path(tempfile.mkdtemp()) / "runs.marker")
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)

        def red_first_artifacts():
            return [r for r in space.events() if r.get("task") == "T1"
                    and r["kind"] == "artifact" and r.get("name") == "red-first"]
        before = red_first_artifacts()

        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        gate=f"echo ran >> {runs}; touch outside.txt; grep -q two a.py",
                        gate_reviewed_first=True, rejections=[], refused_why=None)
        again = loop.run_task(book.task("T1"))

        self.assertEqual("failed", again.state, again.why)
        self.assertIn("outside.txt", again.why)
        self.assertEqual("out_of_scope", book.task("T1")["status"])
        self.assertEqual(1, len(pathlib.Path(runs).read_text().splitlines()))
        # The scope ending must not skip the evidence of what the gate said
        # before it wandered: red_first's return waits for this write.
        self.assertEqual(len(before) + 1, len(red_first_artifacts()))

    def test_a_head_moving_gate_ends_out_of_scope_without_blaming_the_builder(self):
        # This round's gate is the one that moves HEAD, not the builder. A
        # real gate cannot: `lib/hooks/reference-transaction` refuses every
        # ref write from inside the worktree -- `checkout --detach` and
        # `reset --soft` both confirmed refused by hand. The one way
        # HeadMoved still fires is a `git switch` to a branch that already
        # exists, which reattaches HEAD by a symbolic-ref update no hook
        # covers (worktree_refs.py's own docstring) -- simulated here by
        # making judge's own post-gate check raise, standing in for that
        # move. Before the fix this reached `discard`, which blames the
        # builder and charges a rebuild round for a fault the gate caused.
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, _ = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)

        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        gate_reviewed_first=True, rejections=[], refused_why=None)
        # Keyed to judge()'s OWN run_gate call, not a raw call count: red_first
        # checks on_base too (on its own, earlier, clean run of the gate), and
        # counting from zero would arm on the wrong one.
        real_run_gate = loop_judge.run_gate
        real_on_base = Worktree.on_base
        armed = {"on": False}

        def wrapped_run_gate(*a, **kw):
            result = real_run_gate(*a, **kw)
            armed["on"] = True          # the NEXT on_base call is right after THIS gate run
            return result

        def moved_right_after_the_gate(self):
            if armed["on"]:
                armed["on"] = False
                raise HeadMoved("deadbeef")
            return real_on_base(self)

        loop_judge.run_gate = wrapped_run_gate
        Worktree.on_base = moved_right_after_the_gate
        try:
            again = loop.run_task(book.task("T1"))
        finally:
            loop_judge.run_gate = real_run_gate
            Worktree.on_base = real_on_base

        self.assertEqual("failed", again.state, again.why)
        self.assertIn("the gate", again.why)
        self.assertEqual("out_of_scope", book.task("T1")["status"])
        self.assertIsNone(book.task("T1").get("rebuild_from"))   # the tree is gone, so is the pointer
        self.assertEqual(1, book.task("T1")["rebuild_round"])       # not charged a round
        self.assertFalse(pathlib.Path(first.worktree).exists())    # its HEAD was wrong to keep


class FreshTreeGateScopeTest(unittest.TestCase):
    def test_a_first_round_gate_that_proves_red_but_wanders_ends_out_of_scope_before_any_build(self):
        # The ordinary path, not the in-place green one above: a fresh tree,
        # no rebuild round, and the gate comes back red exactly as prove_red
        # wants -- but that same first run also wrote outside.txt. Before the
        # fix nothing checked this run at all: red_first returns None because
        # the gate DID prove red, so the stray file surfaced only inside
        # build()'s own scope check, after paying for a review and a build
        # call neither needed to happen, and blamed "the builder" for a file
        # the gate wrote.
        fakes = Fakes()
        loop, book, _ = loop_for(task(gate="touch outside.txt; grep -q two a.py"), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("failed", out.state, out.why)
        self.assertIn("the gate", out.why)
        self.assertIn("outside.txt", out.why)
        self.assertEqual("out_of_scope", book.task("T1")["status"])
        self.assertEqual([], fakes.calls)   # neither the reviewer nor the builder ran


class ExactGreenWordingTest(unittest.TestCase):
    def test_a_failure_that_merely_mentions_already_passes_is_not_green(self):
        # A timeout or wrong-reason ending can quote the words; only the exact
        # sentence gates.py returns for a green gate may open the in-place path.
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=first.worktree,
                        gate_reviewed_first=True, refused_why=None)
        calls_before = len(fakes.calls)
        wandering = (False, "timeout after 600s; stderr: the gate already passes, so it proves nothing")
        with unittest.mock.patch("loop_evidence.prove_red", return_value=wandering):
            again = loop.run_task(book.task("T1"))
        self.assertNotEqual("done", again.state)
        self.assertEqual("unprovable", book.task("T1")["status"])
        self.assertNotIn("gate_green_in_place", [row["kind"] for row in space.events()])
        self.assertNotIn("build:work", fakes.calls[calls_before:])   # the builder never ran

class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
