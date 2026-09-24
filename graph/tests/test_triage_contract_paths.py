"""Only a refused contract naming its frozen judge gets the path question."""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401
from contract import contract_digest
from providers import Outcome
from test_loop import Fakes, loop_for, task
from test_replan import GOOD, book_with
from triage_paths import contract_path
from turn import replan_pending
from workspace import Workspace

JUDGE = {"id": "J1", "status": "done", "stage": "judge", "files": ["test_a.py"],
         "gate_until_kept": True}


def stalled(**changes):
    book = book_with(triage="contract", needs=["J1"], stage="implement",
                     refused_why="the judge misses the empty case", **changes)
    with book.only_writer():
        document = book.read()
        document["tasks"].append(JUDGE.copy())
        book._write(document)
    space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog=str(book.path))
    space.event("refused", task="T1", step="contract", why=book.task("T1")["refused_why"])
    space.event("released", task="T1")
    return book, space


class ContractPathsTest(unittest.TestCase):
    def test_rewrite_leaves_refused_contract_for_the_replanner(self):
        book, space = stalled()
        book.note("T1", refused_why="this card's gate hides errors; the judge is unchanged")
        before = book.task("T1")
        with mock.patch("triage_jev.ask", return_value=Outcome(
                "ok", verdict="rewrite", confidence=.9)):
            self.assertFalse(contract_path(book, space, before))
        self.assertEqual("refused_contract", book.task("T1")["status"])
        self.assertEqual(before, book.task("T1"))
        decision = next(r for r in space.events() if r["kind"] == "triage_decision")
        self.assertEqual("rewrite", decision["path"])

    def test_slice_answer_sets_needs_slice(self):
        book, space = stalled()
        planner = mock.Mock()
        with mock.patch("triage_jev.ask", return_value=Outcome(
                "ok", verdict="slice", confidence=.9)):
            self.assertTrue(replan_pending(book, space, planner))
        self.assertEqual("needs_slice", book.task("T1")["status"])
        planner.assert_not_called()

    def test_blocked_text_fallback_parks_instead_of_replanning(self):
        import resources
        from distress import INSTRUCTION, TEMPLATE
        from test_distress import BLOCKED
        book, space = stalled()
        planner = mock.Mock()
        with mock.patch("triage_jev.ask", return_value=Outcome("harness")), \
                mock.patch("resources.belt", return_value=[resources.Resource("claude", "work", "opus")]), \
                mock.patch("triage_intelligence._call", return_value=Outcome("ok", text=
                    '{"verdict":"probe_in_gate","why":"rewrite"}\n' + BLOCKED)) as fallback:
            replan_pending(book, space, planner)
            self.assertFalse(replan_pending(book, space, planner))
        self.assertEqual("blocked_by_agent", book.task("T1")["status"])
        self.assertFalse(book.startable())
        self.assertEqual(book.task("T1")["refused_why"], next(e["why"] for e in space.events()
                                          if e["kind"] == "needs_a_person"))
        fallback.assert_called_once()
        planner.assert_not_called()
        self.assertIn(INSTRUCTION + TEMPLATE, fallback.call_args.args[0])


    def test_probe_runs_the_existing_replanner_with_the_probe_instruction(self):
        book, space = stalled()
        planner = mock.Mock(return_value=Outcome("ok", text=GOOD))
        with mock.patch("triage_jev.ask", return_value=Outcome(
                "ok", verdict="probe_in_gate", confidence=.9)) as ask:
            self.assertTrue(replan_pending(book, space, planner))
        self.assertEqual((1, 1), (ask.call_count, planner.call_count))
        self.assertIn("executed probe", planner.call_args.args[0])
        self.assertEqual(("todo", 1), tuple(book.task("T1")[k] for k in ("status", "replans")))
        question = next(r["question"] for r in space.events() if r["kind"] == "triage_decision" and "path" in r)
        self.assertEqual("implement", question["state"]["stage"])
        self.assertEqual("J1", question["state"]["judges"][0]["id"])

    def test_observation_marks_the_contract_seen_and_builds_without_another_contract_review(self):
        fakes = Fakes()
        loop, book, space = loop_for(task(status="refused_contract", triage="contract",
            needs=["J1"], refused_why="the judge ought to be nicer"), fakes, [JUDGE])
        space.event("refused", task="T1", step="contract")
        planner = mock.Mock()
        with mock.patch("triage_jev.ask", return_value=Outcome(
                "ok", verdict="accept_with_observation", confidence=.9)):
            replan_pending(book, space, planner)
        row = book.task("T1")
        self.assertEqual(contract_digest(row), row["contract_seen"])
        self.assertIn("nicer", row["contract_observation"])
        self.assertEqual("todo", row["status"])
        planner.assert_not_called()
        self.assertEqual("done", loop.run_task(row).state)
        self.assertEqual(["build:work", "review"], fakes.calls)

    def test_needs_person_low_gate_and_unknown_hold_with_the_same_question(self):
        for path, confidence in (("needs_person", .9), ("probe_in_gate", .5), ("unknown", .9)):
            with self.subTest(path=path):
                book, space = stalled()
                planner = mock.Mock()
                with mock.patch("triage_jev.ask", return_value=Outcome(
                        "ok", verdict=path, confidence=confidence)):
                    replan_pending(book, space, planner)
                row = book.task("T1")
                self.assertTrue(row["blocked_by_human"])
                self.assertEqual("needs_person", row["held_by"])
                decision = next(r for r in space.events() if r["kind"] == "triage_decision" and "path" in r)
                self.assertEqual(decision["question"], row["path_question"])
                self.assertIn("empty case", row["path_question"]["state"]["refusal"])
                planner.assert_not_called()

    def test_other_endings_and_exhausted_or_held_cards_never_ask(self):
        variants = ({"triage": "work"}, {"refused_why": "a file is missing"},
                    {"needs": []}, {"replans": 6}, {"rebuild_round": 3},
                    {"blocked_by_human": True}, {"gate_has_side_effects": True})
        for changes in variants:
            with self.subTest(changes=changes):
                book, space = stalled()
                book.note("T1", **changes)
                with mock.patch("triage_jev.ask") as ask:
                    self.assertFalse(contract_path(book, space, book.task("T1")))
                ask.assert_not_called()
        for step in ("names", "red_first", "diff_review"):
            book, space = stalled()
            space.event("refused", task="T1", step=step)
            with mock.patch("triage_jev.ask") as ask:
                self.assertFalse(contract_path(book, space, book.task("T1")))
            ask.assert_not_called()

    def test_a_judge_named_by_its_test_file_also_qualifies(self):
        book, space = stalled()
        book.note("T1", refused_why="test_a.py omits empty input")
        with mock.patch("triage_jev.ask", return_value=Outcome(
                "ok", verdict="needs_person", confidence=.9)) as ask:
            contract_path(book, space, book.task("T1"))
        ask.assert_called_once()

    def test_a_hold_raised_during_the_call_is_preserved(self):
        book, space = stalled()

        def answer(*_args):
            book.note("T1", blocked_by_human=True, held_by="owner")
            return Outcome("ok", verdict="accept_with_observation", confidence=.9)

        with mock.patch("triage_jev.ask", side_effect=answer):
            contract_path(book, space, book.task("T1"))
        self.assertEqual("owner", book.task("T1")["held_by"])
        self.assertNotIn("contract_seen", book.task("T1"))


if __name__ == "__main__":
    unittest.main()
