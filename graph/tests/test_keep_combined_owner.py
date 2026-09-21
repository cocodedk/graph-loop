"""A combined-gate failure is charged to whoever is at fault, not to whoever
owns the gate.

The keeper re-runs the gates of the cards already kept on the tree the branch
would hold. When one of THOSE goes red, owning it is not the same as being at
fault: red on the branch tip WITHOUT this card's work is the gate's own defect
and no builder of this card can answer it, while green there and red beside
the diff is a regression this card caused. The rig lives in `test_loop`.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from gates import GateResult
from keep_failure import GateFailure
from loop import Loop
from test_loop import Fakes, repo_with, task

EXPECTED_TESTS = 7

# Kept before this card and STILL GREEN on the branch tip: a.py says "one"
# there. It goes red only beside this card's diff, which makes it a regression
# this card's builder caused.
# The grant names the affected file, so scoped selection reaches attribution.
OLDER = {"id": "T0", "goal": "a.py says one", "status": "done", "needs": [],
         "files": ["a.py"], "gate": "grep -q one a.py", "done_when": "a.py says one",
         "kept_at": "2026-08-30T10:00:00Z"}

# Red on the branch tip on its own, with or without this card's diff: the gate
# itself is what needs repairing, and no builder of another card can do it.
BROKEN = {**OLDER, "id": "T9", "goal": "a file that is not there",
          "gate": "test -f never-here", "done_when": "the file is there"}


def keeper_loop(row: dict, fakes: Fakes, extra: list):
    root, book, space = repo_with(row, extra)
    return Loop(repo=root, backlog=book, space=space, build=fakes.builder,
                review=fakes.reviewer, branch="campaign/test"), book, space


class OtherCardsGateTest(unittest.TestCase):
    def test_a_kept_red_first_judge_keeps_its_regression_check(self):
        judge = {**OLDER, "gate": "! grep -q two a.py", "gate_until_kept": True,
                 "gate_when_kept": "grep -q two a.py"}
        fakes = Fakes()
        later = task(id="T2", gate="grep -q three a.py", needs=["T1"])
        loop, book, _ = keeper_loop(task(), fakes, [judge, later])
        delivered = loop.run_task(book.task("T1"))
        self.assertEqual("done", delivered.state, delivered.why)
        self.assertEqual("done", book.task("T0")["status"])
        # A later card's own gate accepts the regression; the lasting judge does not.
        book.note("T1", gate_until_kept=True, gate_when_kept=None)
        fakes.edit = "three\n"
        regressed = loop.run_task(book.task("T2"))
        self.assertEqual("rejected", regressed.state, regressed.why)
        self.assertEqual(1, book.task("T2")["rebuild_round"])
        self.assertIn(judge["gate_when_kept"], regressed.why)
        self.assertEqual("done", book.task("T0")["status"])

    def test_a_gate_red_without_this_work_is_routed_to_its_owner_uncharged(self):
        fakes = Fakes()
        loop, book, space = keeper_loop(task(), fakes, [BROKEN])
        out = loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertEqual(0, int(row.get("rebuild_round") or 0))   # not this card's round
        self.assertEqual("todo", row["status"])                   # it runs again
        self.assertEqual(out.worktree, row["rebuild_from"])       # in the tree it paid for
        self.assertTrue(pathlib.Path(out.worktree).is_dir())
        clash = [e for e in space.events() if e.get("kind") == "failed"
                 and e.get("step") == "combined_gate"]
        self.assertEqual(["T9"], [e["gate_owner"] for e in clash])

    def test_a_finished_owner_is_never_reopened_and_the_dependent_is_parked(self):
        """T9 stayed done with its gate red, and reopening finished work for a
        defect this card's builder cannot answer would only spend new rounds
        retrying into the same red gate — the owner would settle `done` again
        the moment the repair lands, so `needs` could never tell the two cards
        apart. The owner is left exactly as it was, and this card is parked
        for a person to make the new decision the defect calls for."""
        fakes = Fakes()
        loop, book, _ = keeper_loop(task(), fakes, [BROKEN])
        loop.run_task(book.task("T1"))
        self.assertEqual(BROKEN, book.task("T9"))               # untouched, still done
        row = book.task("T1")
        self.assertTrue(row["blocked_by_human"])                # parked, not requeued to spin
        self.assertIn("red on the branch tip", row["refused_why"])
        self.assertNotIn("T1", [r["id"] for r in book.startable()])

    def test_a_held_owner_stays_untouched_too(self):
        """A person's hold on a finished owner is not even reached: the owner
        is never written to at all when it is already `done`."""
        fakes = Fakes()
        held = {**BROKEN, "blocked_by_human": True, "gate_rounds": 2}
        loop, book, _ = keeper_loop(task(), fakes, [held])
        loop.run_task(book.task("T1"))
        self.assertEqual(held, book.task("T9"))                 # not written to at all
        row = book.task("T1")
        self.assertTrue(row["blocked_by_human"])
        self.assertNotIn("T1", [r["id"] for r in book.startable()])

    def test_a_gate_this_work_turned_red_is_the_builders_own_regression(self):
        """Owning the gate is not being at fault. T0's gate passes on the
        branch tip and fails only beside this card's diff: this card broke it,
        and routing the repair to T0 would leave the branch red for ever."""
        fakes = Fakes()
        loop, book, space = keeper_loop(task(), fakes, [OLDER])
        loop.run_task(book.task("T1"))
        self.assertEqual(1, book.task("T1")["rebuild_round"])   # charged, as a rejection is
        self.assertEqual([], [e for e in space.events()
                              if e.get("step") == "combined_gate"])

    def test_this_cards_own_gate_still_charges_it(self):
        """The combined check runs this card's gate too, last in the list.
        That failure IS its own, and it costs a round as it always did.

        The failing gate is chosen here rather than arranged in a fixture:
        with `gates[-1]` (this card's) the round is charged; swapping it for
        `OLDER["gate"]` makes this case fail, which is what tells the two
        branches apart.
        """
        fakes = Fakes()
        loop, book, space = keeper_loop(task(), fakes, [OLDER])
        loop.keeper._combined_tree_red = lambda task_id, commit, gates: GateFailure(
            gates[-1], GateResult(1, "red on the branch"), commit, "")
        loop.run_task(book.task("T1"))
        self.assertEqual(1, book.task("T1")["rebuild_round"])
        self.assertEqual([], [e for e in space.events()
                              if e.get("step") == "combined_gate"])

    def test_a_probe_that_proves_nothing_retries_the_check_without_rebuilding(self):
        # Retires the earlier rule: unavailable baseline evidence is a harness fault,
        # never proof that the builder caused a regression.
        fakes = Fakes()
        loop, book, space = keeper_loop(task(), fakes, [BROKEN])
        real = loop.keeper._combined_tree_red

        def probe(task_id, commit, gates):
            if commit == loop.keeper.tip():          # the defect probe, not the keep's own
                raise RuntimeError("the tip could not be checked out")
            return real(task_id, commit, gates)

        loop.keeper._combined_tree_red = probe
        outcome = loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertEqual("harness", outcome.state)
        self.assertEqual("gate", row["finished"]["phase"])
        self.assertEqual(outcome.worktree, row["rebuild_from"])
        self.assertEqual("done", book.task("T9")["status"])
        self.assertNotIn("T9", row["needs"])
        self.assertIn("gate_defect_unproved", [e["kind"] for e in space.events()])
        loop.run_task(book.task("T1"))
        self.assertEqual(1, sum(call.startswith("build:") for call in fakes.calls))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
