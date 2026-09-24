"""Accepted-criteria stalls keep the paid diff or allow one reviewed rewrite."""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
from accepted_contract import changed_criteria
from contract import contract_digest
from providers import Outcome
from replan import replan, replan_until_planned
from test_loop import Fakes, loop_for, task
from test_replan import GOOD
from triage_paths import criteria_path
from turn import replan_pending

ACCEPT = Outcome("ok", verdict="ACCEPT", text="accepted")
REJECT = Outcome("ok", verdict="REJECT", text="the accepted criteria should check another input")
REWRITE = GOOD.replace("grep -q two a.py", "test \"$(cat a.py)\" = two")


def stalled():
    fakes = Fakes(review=[ACCEPT, REJECT])
    loop, book, space = loop_for(task(), fakes)
    out = loop.run_task(book.task("T1"))
    assert out.state == "rejected", out
    book.set_status("T1", "refused_contract", triage="contract",
                    refused_why=book.task("T1")["diff_review_refusal"]["findings"])
    return loop, book, space, fakes


class CriteriaPathsTest(unittest.TestCase):
    def run_path(self, book, space, path, **kwargs):
        planner = mock.Mock(return_value=Outcome("ok", text=REWRITE))
        with mock.patch("triage_jev.ask", return_value=Outcome(
                "ok", verdict=path, confidence=kwargs.get("confidence", .9))) as ask:
            replan_pending(book, space, planner)
        return planner, ask

    def test_accept_change_resumes_the_exact_diff_through_the_gate_without_rebuilding(self):
        loop, book, space, fakes = stalled()
        original = book.task("T1")
        planner, ask = self.run_path(book, space, "accept_change")
        row = book.task("T1")
        self.assertEqual((1, 1), (planner.call_count, ask.call_count))
        self.assertEqual("todo", row["status"])
        self.assertEqual(original["accepted_criteria"], row["accepted_criteria"])
        self.assertEqual(1, row["replans"])
        self.assertEqual(original["rebuild_round"], row["rebuild_round"])
        self.assertIn("another input", row["review_observation"])
        before = list(fakes.calls)
        self.assertEqual("done", loop.run_task(row).state)
        self.assertEqual(before, fakes.calls)
        self.assertNotIn("accepted_diff", book.task("T1"))
        gates = [r for r in space.events() if r.get("step") == "gate"]
        self.assertEqual(2, len(gates))
        evidence = next(r["question"]["state"] for r in space.events() if r["kind"] == "triage_decision" and "path" in r)
        self.assertTrue(evidence["changed_criteria_would_refuse"])
        self.assertEqual(original["contract_seen"], evidence["accepted_criteria_digest"])

    def test_reopen_clears_acceptance_for_one_replan_then_reviews_again(self):
        loop, book, space, fakes = stalled()
        snapshots = []

        def planner(_prompt, _resource):
            snapshots.append(book.task("T1"))
            return Outcome("ok", text=REWRITE)

        with mock.patch("triage_jev.ask", return_value=Outcome(
                "ok", verdict="reopen_contract", confidence=.9)) as ask:
            replan_pending(book, space, planner)
        self.assertEqual(2, len(snapshots))
        ask.assert_called_once()
        self.assertNotIn("contract_seen", snapshots[1])
        self.assertNotIn("accepted_criteria", snapshots[1])
        row = book.task("T1")
        self.assertEqual(("todo", 2, True), tuple(row[k] for k in
                         ("status", "replans", "gate_reviewed_first")))
        self.assertEqual(snapshots[0]["requirement"], row["requirement"])
        fakes.review = [ACCEPT]
        before = len(fakes.calls)
        self.assertEqual("done", loop.run_task(row).state)
        self.assertEqual(["review", "build:work", "review"], fakes.calls[before:])
        self.assertEqual(contract_digest(book.task("T1")), book.task("T1")["contract_seen"])

    def test_person_unknown_and_low_confidence_preserve_acceptance_and_hold(self):
        for path, confidence in (("needs_person", .9), ("unknown", .9), ("accept_change", .5)):
            with self.subTest(path=path):
                _, book, space, _ = stalled()
                saved = book.task("T1")["accepted_criteria"]
                planner, _ = self.run_path(book, space, path, confidence=confidence)
                row = book.task("T1")
                self.assertEqual("needs_person", row["held_by"])
                self.assertTrue(row["blocked_by_human"])
                self.assertEqual(saved, row["accepted_criteria"])
                self.assertIn("findings", row["path_question"]["state"])
                self.assertEqual(1, planner.call_count)

    def test_other_replan_refusals_and_budget_limits_do_not_ask(self):
        for changes in ({"diff_review_refusal": None, "rejections": None}, {"replans": 5},
                        {"blocked_by_human": True}, {"gate_has_side_effects": True}):
            with self.subTest(changes=changes):
                _, book, space, _ = stalled()
                book.note("T1", **changes)
                _, ask = self.run_path(book, space, "accept_change")
                ask.assert_not_called()
        _, book, space, _ = stalled()
        with mock.patch("triage_jev.ask") as ask:
            replan_until_planned(book, book.task("T1"), lambda _: Outcome("capacity"), space=space)
            replan_until_planned(book, book.task("T1"), lambda _: Outcome("ok", text="bad"), space=space)
        ask.assert_not_called()

    def test_changed_diff_invalidates_accept_change(self):
        loop, book, space, fakes = stalled()
        self.run_path(book, space, "accept_change")
        (pathlib.Path(book.task("T1")["rebuild_from"]) / "a.py").write_text("two two\n")
        fakes.edit, fakes.review = None, [ACCEPT]
        before = len(fakes.calls)
        self.assertEqual("done", loop.run_task(book.task("T1")).state)
        self.assertEqual(["build:work", "review"], fakes.calls[before:])

    def test_a_new_hold_wins_over_reopening(self):
        _, book, space, _ = stalled()
        proposed = {"gate": "new gate"}
        book.note("T1", refused_why=changed_criteria(book.task("T1"), proposed),
                  refused_rewrite=proposed)

        def answer(*_args):
            book.note("T1", blocked_by_human=True, held_by="owner")
            return Outcome("ok", verdict="reopen_contract", confidence=.9)

        with mock.patch("triage_jev.ask", side_effect=answer):
            criteria_path(book, space, book.task("T1"))
        self.assertEqual("owner", book.task("T1")["held_by"])
        self.assertIn("accepted_criteria", book.task("T1"))

    def test_recorded_choice_is_applied_after_restart_before_another_planner_call(self):
        _, book, space, _ = stalled()
        with mock.patch("triage_paths.hold", side_effect=RuntimeError("process died")), \
                self.assertRaises(RuntimeError):
            self.run_path(book, space, "needs_person")
        self.assertEqual(1, book.task("T1")["replans"])
        planner, ask = self.run_path(book, space, "accept_change")
        planner.assert_not_called()
        ask.assert_not_called()
        self.assertEqual("needs_person", book.task("T1")["held_by"])

    def test_existing_card_uses_its_recorded_diff_review_and_matching_artifact(self):
        loop, book, space, fakes = stalled()
        replan(book, book.task("T1"), lambda _: Outcome("ok", text=REWRITE))
        space.artifact("T1", "replan-answer", REWRITE)
        book.note("T1", diff_review_refusal=None, refused_rewrite=None)
        planner, _ = self.run_path(book, space, "accept_change")
        planner.assert_not_called()
        before = list(fakes.calls)
        self.assertEqual("todo", book.task("T1")["status"])
        self.assertEqual("done", loop.run_task(book.task("T1")).state)
        self.assertEqual(before, fakes.calls)


if __name__ == "__main__":
    unittest.main()
