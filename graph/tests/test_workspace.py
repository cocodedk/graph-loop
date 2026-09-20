"""The campaign's own record: events that only append, attempts, holds and pids.

Written before `workspace.py`. The rules under test: a crash must never let the
loop repeat a commit or lose a running task, a limit must never be filed as an
attempt, and `stop --now` must be able to find every process it started.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from workspace import Workspace

EXPECTED_TESTS = 18


def fresh() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="backlog.yaml")


class RecordTest(unittest.TestCase):
    def test_an_event_is_appended_and_never_rewritten(self):
        space = fresh()
        space.event("started", task="T1")
        space.event("finished", task="T1", commit="abc")
        rows = space.events()
        self.assertEqual(["init", "started", "finished"], [row["kind"] for row in rows])
        self.assertEqual("abc", rows[-1]["commit"])

    def test_every_event_carries_the_time_it_happened(self):
        space = fresh()
        space.event("started", task="T1")
        self.assertRegex(space.events()[-1]["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")

    def test_an_active_turn_context_owns_event_provenance(self):
        space = fresh()
        space.turn_id = "turn-7"
        space.event("inside", turn="turn-forged")
        space.turn_id = ""
        space.event("outside")
        rows = space.events()
        self.assertEqual("turn-7", rows[-2].get("turn"))
        self.assertNotIn("turn", rows[-1])

    def test_a_reopened_workspace_reads_what_the_last_one_wrote(self):
        space = fresh()
        space.event("started", task="T1")
        again = Workspace(space.root)
        self.assertEqual(2, len(again.events()))


class AttemptTest(unittest.TestCase):
    def test_an_answered_call_is_filed_as_an_attempt(self):
        space = fresh()
        space.attempt("T1", account="work", kind="ok", cost=1.5, tokens=100)
        self.assertEqual(1, space.attempts("T1"))

    def test_a_limit_or_a_denial_is_recorded_but_is_not_an_attempt(self):
        space = fresh()
        space.attempt("T1", account="work", kind="limit")
        space.attempt("T1", account="work", kind="harness")
        self.assertEqual(0, space.attempts("T1"))
        self.assertEqual(3, len(space.events()))

    def test_two_answered_failures_of_the_same_task_ask_for_a_slice(self):
        space = fresh()
        space.attempt("T1", account="work", kind="ok", failed_gate=True)
        space.event("failed", task="T1", step="gate", why="still red")
        self.assertFalse(space.needs_slice("T1"))
        space.attempt("T1", account="personal", kind="ok", failed_gate=True)
        space.event("failed", task="T1", step="gate", why="still red")
        self.assertTrue(space.needs_slice("T1"))


class ProcessTest(unittest.TestCase):
    def test_a_running_task_is_visible_with_its_process_group(self):
        space = fresh()
        here = os.getpgid(0)
        space.claim("T1", pgid=here, account="work", worktree="/tmp/x")
        self.assertEqual({"T1"}, set(space.running()))
        self.assertEqual(here, space.running()["T1"]["pgid"])

    def test_a_released_task_is_no_longer_running(self):
        space = fresh()
        space.claim("T1", pgid=os.getpgid(0), account="work", worktree="/tmp/x")
        space.release("T1")
        self.assertEqual({}, space.running())

    def test_a_claim_survives_the_process_that_made_it(self):
        space = fresh()
        space.claim("T1", pgid=os.getpgid(0), account="work", worktree="/tmp/x")
        self.assertEqual({"T1"}, set(Workspace(space.root).running()))


class RotationTest(unittest.TestCase):
    def test_the_event_log_rotates_so_no_file_grows_huge(self):
        space = fresh()
        space.max_events_per_file = 5
        for number in range(12):
            space.event("tick", n=number)
        parts = sorted(p.name for p in pathlib.Path(space.root).glob("events*.jsonl"))
        self.assertGreater(len(parts), 2, parts)
        for part in parts:
            lines = (pathlib.Path(space.root) / part).read_text().splitlines()
            self.assertLessEqual(len(lines), 5, part)

    def test_reading_gathers_every_part_in_order(self):
        space = fresh()
        space.max_events_per_file = 3
        for number in range(10):
            space.event("tick", n=number)
        ticks = [row["n"] for row in space.events() if row["kind"] == "tick"]
        self.assertEqual(list(range(10)), ticks)

    def test_a_rotated_campaign_still_counts_its_attempts(self):
        space = fresh()
        space.max_events_per_file = 2
        for _ in range(4):
            space.attempt("T1", account="work", kind="ok")
        self.assertEqual(4, space.attempts("T1"))


class EventsCacheTest(unittest.TestCase):
    @mock.patch("workspace.json.loads", wraps=json.loads)
    def test_a_second_call_with_no_writes_does_not_reparse(self, loads):
        space = fresh()
        space.event("started", task="T1")
        first = space.events()
        self.assertEqual(2, len(first))
        loads.reset_mock()
        second = space.events()
        self.assertEqual(0, loads.call_count)   # nothing wrote: the cache answers
        self.assertEqual(first, second)
        loads.reset_mock()
        space.event("finished", task="T1")
        third = space.events()
        self.assertGreater(loads.call_count, 0)   # a write invalidates the cache
        self.assertEqual("finished", third[-1]["kind"])


class AlertTest(unittest.TestCase):
    def test_an_alert_is_written_where_a_person_will_see_it(self):
        space = fresh()
        space.alert("T1", "the builder stopped: it needs a decision")
        self.assertEqual(1, len(space.alerts()))
        self.assertIn("needs a decision", space.alerts()[0])

    def test_two_alerts_with_the_same_words_are_both_shown(self):
        space = fresh()
        space.alert("T1", "the builder stopped")
        space.alerts_read(len(space.alerts()))
        space.alert("T1", "the builder stopped")   # same words, new event
        self.assertEqual(1, len(space.alerts()))

    def test_alerts_already_read_are_not_shown_again(self):
        space = fresh()
        space.alert("T1", "first")
        space.alerts_read(len(space.alerts()))
        self.assertEqual([], space.alerts())
        space.alert("T2", "second")
        self.assertEqual(1, len(space.alerts()))
        self.assertIn("second", space.alerts()[0])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
