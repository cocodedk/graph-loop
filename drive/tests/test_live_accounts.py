"""A live task is called once — unless the call never reached the model.

One expired account quarantined every live card in the campaign, turn after
turn: live tasks were pinned to the first account, and that account's session
had expired. A refused session is proof the model never ran, so no helper verb
ran either and there is nothing to repeat, and nothing to inspect.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 12

LIVE = {"gate_has_side_effects": True, "helper_verbs": ["journal"]}


class ALiveTaskIsCalledOnce(unittest.TestCase):
    def test_a_crash_never_reaches_a_second_account(self):
        """The call may have run a helper verb: a retry would repeat a live action."""
        fakes = Fakes(build=[Outcome("crash", text="boom"), Outcome("ok", text="done")])
        loop, book, _ = loop_for(task(**LIVE), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual(1, len([c for c in fakes.calls if c.startswith("build:")]))
        self.assertEqual("live_call_lost", book.task("T1")["status"])

    def test_a_refused_session_tries_the_other_account(self):
        fakes = Fakes(build=[Outcome("auth", text="expired", cost=0, tokens=0), Outcome("ok", text="done")])
        loop, book, _ = loop_for(task(**LIVE), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual(2, len([c for c in fakes.calls if c.startswith("build:")]),
                         "the belt was not walked to the resource that answered")

    def test_every_account_refused_blames_the_sign_in_and_not_the_stack(self):
        fakes = Fakes(build=[Outcome("auth", text="expired", cost=0, tokens=0), Outcome("auth", text="expired", cost=0, tokens=0)])
        loop, book, _ = loop_for(task(**LIVE), fakes)
        out = loop.run_task(book.task("T1"))
        row = book.task("T1")
        self.assertIn("never reached the model", row["refused_why"])
        self.assertIn("untouched", row["refused_why"])
        self.assertNotIn("half-done", str(row["refused_why"]) + out.why)
        self.assertNotEqual("live_call_lost", row["status"], "the stack was never in doubt")
        self.assertEqual("", out.worktree, "no model ran: there is no worktree to keep")

    def test_a_refused_session_holds_the_card_and_frees_the_peers_it_held(self):
        """The card waits for a sign-in rather than being picked again at once, and
        the live peers this call held go back to the queue: the stack never moved."""
        fakes = Fakes(build=[Outcome("auth", text="expired", cost=0, tokens=0), Outcome("auth", text="expired", cost=0, tokens=0)])
        peer = task(id="T2", **LIVE)
        loop, book, _ = loop_for(task(**LIVE), fakes, [peer])
        loop.run_task(book.task("T1"))
        self.assertTrue(book.task("T1").get("blocked_by_human"), "a card that cannot sign in must wait")
        self.assertIn("T1", [row["id"] for row in book.waiting_for_human()],
                      "the board must show it as waiting for a person")
        self.assertNotIn("T1", [row["id"] for row in book.startable()],
                         "a held card must not be picked again on the next turn")
        self.assertEqual("todo", book.task("T2")["status"], "the peer was held for a stack that never moved")
        self.assertFalse(book.task("T2").get("blocked_by_human"))

    def test_a_refused_session_that_spent_something_is_treated_as_a_live_call(self):
        """`kind` comes from matching the answer's text, and text does not prove no
        tool ran. Only a call that spent nothing did nothing."""
        fakes = Fakes(build=[Outcome("auth", text="expired", cost=0.4, tokens=900),
                             Outcome("ok", text="done")])
        loop, book, _ = loop_for(task(**LIVE), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual(1, len([c for c in fakes.calls if c.startswith("build:")]))
        self.assertEqual("live_call_lost", book.task("T1")["status"])

    def test_a_peer_already_held_for_a_person_keeps_its_hold(self):
        fakes = Fakes(build=[Outcome("auth", text="expired", cost=0, tokens=0), Outcome("auth", text="expired", cost=0, tokens=0)])
        peer = task(id="T2", blocked_by_human=True, **LIVE)
        loop, book, _ = loop_for(task(**LIVE), fakes, [peer])
        loop.run_task(book.task("T1"))
        self.assertTrue(book.task("T2").get("blocked_by_human"),
                        "another decision's hold is not this call's to release")

    def test_a_rebuild_round_keeps_the_tree_that_holds_its_earlier_work(self):
        """A rebuild round reuses its worktree; the rounds before it live there."""
        first = Fakes(build=[Outcome("crash", text="boom")])
        loop, book, _ = loop_for(task(), first)          # a code task, so it can be rebuilt
        out = loop.run_task(book.task("T1"))
        book.set_status("T1", "todo", rebuild_round=1, rebuild_from=out.worktree,
                        gate_has_side_effects=True, helper_verbs=["journal"])
        self.assertTrue((pathlib.Path(out.worktree) / ".git").exists(), "no tree to reuse")
        again = Fakes(build=[Outcome("auth", text="expired", cost=0, tokens=0), Outcome("auth", text="expired", cost=0, tokens=0)])
        loop.build = again.builder
        second = loop.run_task(book.task("T1"))
        self.assertEqual(out.worktree, second.worktree, "the rebuild tree was thrown away")
        self.assertTrue((pathlib.Path(out.worktree) / ".git").exists(), "the earlier work is gone")

    def test_a_limit_reached_before_the_first_turn_tries_the_other_account(self):
        """The work account runs out mid-campaign; a limit refused before any turn
        spent nothing, so the live card is not stranded until someone notices."""
        fakes = Fakes(build=[Outcome("limit", text="hit your weekly limit", cost=0, tokens=0), Outcome("ok", text="done")])
        loop, book, _ = loop_for(task(**LIVE), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual(2, len([c for c in fakes.calls if c.startswith("build:")]),
                         "the belt was not walked to the resource that answered")

    def test_a_limit_reached_part_way_through_is_treated_as_a_live_call(self):
        fakes = Fakes(build=[Outcome("limit", text="hit your weekly limit", cost=0.6, tokens=1200),
                             Outcome("ok", text="done")])
        loop, book, _ = loop_for(task(**LIVE), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual(1, len([c for c in fakes.calls if c.startswith("build:")]))
        self.assertEqual("live_call_lost", book.task("T1")["status"])

    def test_a_refusal_whose_numbers_are_missing_is_not_proof_of_nothing(self):
        """An answer that carries no cost and no token count says nothing about what
        it did. Unknown is not zero, and a live task does not retry on unknown."""
        fakes = Fakes(build=[Outcome("auth", text="expired"), Outcome("ok", text="done")])
        loop, book, _ = loop_for(task(**LIVE), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual(1, len([c for c in fakes.calls if c.startswith("build:")]))
        self.assertEqual("live_call_lost", book.task("T1")["status"])

    def test_a_code_task_walks_the_belt_on_a_resource_refusal(self):
        fakes = Fakes(build=[Outcome("capacity", text="at capacity", cost=0, tokens=0),
                             Outcome("ok", text="done")])
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual(2, len([c for c in fakes.calls if c.startswith("build:")]))

    def test_a_code_task_does_not_walk_the_belt_on_a_crash(self):
        """The resource answered; another would spend money repeating the failure."""
        fakes = Fakes(build=[Outcome("crash", text="boom"), Outcome("ok", text="done")])
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        self.assertEqual(1, len([c for c in fakes.calls if c.startswith("build:")]))


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
