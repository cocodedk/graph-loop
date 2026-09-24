"""The worst thing the loop can do while nobody is watching: pay a builder
for an answer and never keep it. Split from `test_doctor` at the 200-line
cap. The rig is `test_doctor`'s."""

from __future__ import annotations

import pathlib
import sys
import unittest

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from doctor import check_costly_silence, diagnose
from test_doctor import book, space

EXPECTED_TESTS = 15


class SalvageTest(unittest.TestCase):
    def test_work_that_was_paid_for_and_never_kept_is_named(self):
        # The night's worst defect: a builder finished, and the loop dropped it.
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=2.73)
        out = check_costly_silence(here)
        self.assertEqual(1, len(out))
        self.assertIn("never kept", out[0].what)
        here.event("accepted", task="T1")
        self.assertEqual([], check_costly_silence(here))

    def test_work_that_still_sits_in_its_worktree_is_not_lost(self):
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=9.0)
        here.event("worktree", task="T1", path=str(pathlib.Path(__file__).parent))   # it exists
        self.assertEqual([], check_costly_silence(here))

    def test_a_planner_call_is_never_unkept_work(self):
        here = space()
        here.attempt("T1", account="plan", kind="ok", cost=1.2)
        self.assertEqual([], check_costly_silence(here))

    def test_a_review_call_is_never_unkept_work(self):
        # A review answers about a build; it never keeps one, so it must
        # not be charged as work paid for and thrown away.
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=2.0, purpose="review")
        self.assertEqual([], check_costly_silence(here))
        plain = space()
        plain.attempt("T1", account="work", kind="ok", cost=2.0)
        self.assertEqual(1, len(check_costly_silence(plain)))

    def test_plan_account_not_triage_purpose_exempts_a_call(self):
        # Triage reads one failed ending; it does not build work to keep.
        here = space()
        here.attempt("the triage", account="plan", kind="ok", cost=2.0,
                     purpose="triage")
        self.assertEqual([], check_costly_silence(here))
        plain = space()
        plain.attempt("the triage", account="work", kind="ok", cost=2.0,
                      purpose="triage")
        self.assertEqual(1, len(check_costly_silence(plain)))

    def test_many_rounds_of_one_task_are_one_line_with_the_total(self):
        here = space()
        for cost in (25.0, 11.4, 6.0):
            here.attempt("T1", account="work", kind="ok", cost=cost)
        here.event("worktree", task="T1", path="/tmp/gone-with-the-round")           # removed
        out = check_costly_silence(here)
        self.assertEqual(1, len(out))
        self.assertIn("3 builder answers never kept", out[0].what)
        self.assertIn("$42.40", out[0].what)

    def test_a_sliced_task_is_answered_for_only_by_a_successor_that_names_it(self):
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=9.5)
        orphan = book(status="sliced")
        self.assertEqual(1, len([c for c in diagnose(orphan, here) if "never kept" in c.what]))
        with_child = book(status="sliced")
        doc = yaml.safe_load(with_child.path.read_text())
        doc["tasks"].append({"id": "T1.v2", "goal": "again", "status": "todo", "needs": [], "files": ["simulation/a.py"],
                             "gate": "true", "done_when": "x", "sliced_from": "T1"})
        with_child.path.write_text(yaml.safe_dump(doc, sort_keys=False))
        self.assertEqual([], [c for c in diagnose(with_child, here) if "never kept" in c.what])

    def test_a_sliced_task_cannot_certify_itself(self):
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=9.5)
        selfie = book(status="sliced", sliced_from="T1")
        self.assertEqual(1, len([c for c in diagnose(selfie, here) if "never kept" in c.what]))

    def test_a_sliced_row_without_an_id_does_not_stop_the_doctor(self):
        here = space()
        headless = book(status="sliced")
        doc = yaml.safe_load(headless.path.read_text()); del doc["tasks"][0]["id"]
        headless.path.write_text(yaml.safe_dump(doc, sort_keys=False))
        diagnose(headless, here)   # no KeyError

    def test_an_id_less_successor_certifies_nothing(self):
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=9.5)
        sliced = book(status="sliced")
        doc = yaml.safe_load(sliced.path.read_text())
        doc["tasks"].append({"goal": "again", "status": "todo", "sliced_from": "T1"})   # no id
        sliced.path.write_text(yaml.safe_dump(doc, sort_keys=False))
        self.assertEqual(1, len([c for c in diagnose(sliced, here) if "never kept" in c.what]))

    def test_a_drop_answers_for_the_attempts_before_it_only(self):
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=9.5)
        here.event("dropped", task="T1", why="re-sliced")
        here.attempt("T1", account="work", kind="ok", cost=3.0)
        self.assertEqual(1, len(check_costly_silence(here)))

    def test_a_drop_that_says_why_is_an_answer(self):
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=9.5)
        here.event("dropped", task="T1", why="its three rounds became T1.v2's design")
        self.assertEqual([], check_costly_silence(here))

    def test_a_drop_without_a_why_is_still_a_complaint(self):
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=9.5)
        here.event("dropped", task="T1", why="")
        self.assertEqual(1, len(check_costly_silence(here)))

    def test_a_queued_rebuild_is_moving_until_any_ending_strands_it_again(self):
        here = space()
        here.attempt("T1", account="work", kind="ok", cost=2.73)
        here.event("rebuild_queued", task="T1", round=1, why="fix one thing")
        self.assertEqual([], check_costly_silence(here))       # the builder has it
        here.event("failed", task="T1", step="scope", why="wrote outside its files")
        self.assertEqual(1, len(check_costly_silence(here)))   # stranded again


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
