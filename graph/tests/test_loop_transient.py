"""A server outage preserves cards and uses the driver's one shared pause."""

from __future__ import annotations

import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import Outcome
from test_driver import graph_goal
from test_loop import Fakes, loop_for, task
from test_provider_transient import answer
from watchdog import check


class TransientLoopTest(unittest.TestCase):
    def test_a_500_never_spends_the_last_round_and_the_card_can_finish(self):
        out = answer(api_error_status=500, result="API Error: 500 Internal server error")
        fakes = Fakes(build=[out])
        loop, book, space = loop_for(task(rebuild_round=2), fakes)
        for _ in range(4):
            result = loop.run_task(book.task("T1"))
            card = book.task("T1")
            self.assertEqual(("todo", 2), (card["status"], card["rebuild_round"]))
            self.assertEqual(result.worktree, card["rebuild_from"])
            self.assertEqual("kept-session", card["session"])
        queued = [row for row in space.events() if row["kind"] == "rebuild_queued"]
        self.assertEqual([False] * 4, [row["charged"] for row in queued])
        self.assertFalse(check(space).spinning)
        self.assertFalse(any(row["kind"] in ("rejected", "quarantined", "needs_a_person")
                             for row in space.events()))
        fakes.build = [Outcome("ok", text="DONE")]
        self.assertEqual("done", loop.run_task(book.task("T1")).state)

    def test_a_500_before_work_preserves_rounds_and_status(self):
        out = answer(api_error_status=500, total_cost_usd=0,
                     usage={"input_tokens": 0, "output_tokens": 0})
        loop, book, _ = loop_for(task(rebuild_round=2), Fakes(build=[out]))
        self.assertEqual("waiting", loop.run_task(book.task("T1")).state)
        self.assertEqual(("todo", 2), (book.task("T1")["status"], book.task("T1")["rebuild_round"]))

    def test_a_genuine_crash_still_spends_the_last_round(self):
        loop, book, _ = loop_for(task(rebuild_round=2), Fakes(build=[answer(returncode=-9)]))
        self.assertEqual("rejected", loop.run_task(book.task("T1")).state)
        self.assertEqual(("rejected", 3), (book.task("T1")["status"], book.task("T1")["rebuild_round"]))

    def test_a_diff_review_500_preserves_rounds_and_paid_work(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              answer(api_error_status=500)])
        loop, book, _ = loop_for(task(rebuild_round=2), fakes)
        result = loop.run_task(book.task("T1"))
        card = book.task("T1")
        self.assertEqual(("todo", 2, result.worktree),
                         (card["status"], card["rebuild_round"], card["rebuild_from"]))
        self.assertEqual("two\n", (pathlib.Path(result.worktree) / "a.py").read_text())

    def test_two_cards_share_one_cooldown_and_alert_before_retrying(self):
        # One transient and one limit use the SAME wait; neither owns a timer.
        outages = [answer(api_error_status=500), answer(result="HTTP 429")]
        fakes = Fakes()
        loop, book, space = loop_for(task(rebuild_round=2), fakes,
                                     [task(id="T2", files=["b.py"], rebuild_round=2,
                                           gate="test -f b.py")])
        (space.root / "approved").touch()
        calls, pauses = [], []

        def builder(prompt, *, cwd, files, **kwargs):
            calls.append(files[0])
            if not pauses:
                return outages[0 if files[0] == "a.py" else 1]
            (pathlib.Path(cwd) / files[0]).write_text("two\n")
            return Outcome("ok", text="DONE")

        def idle(seconds):
            self.assertEqual(2, len(calls))
            self.assertEqual([("todo", 2)] * 2,
                             [(row["status"], row["rebuild_round"]) for row in book.tasks()])
            # The cooldown's own alert, not every alert this run may carry: a
            # launch directory in another repository writes one of its own.
            alerts = [row for row in space.events()
                      if row["kind"] == "alert" and row["task"] == "the campaign"]
            self.assertEqual(1, len(alerts))
            pauses.append(seconds)

        loop.build = builder
        args = types.SimpleNamespace(dry_run=False, lanes=2, max_tasks=4,
                                     idle_seconds=300, attempt_ceiling=12, hours_ceiling=2.0)
        with patch.object(graph_goal, "_space", return_value=space), \
             patch.object(graph_goal, "Loop", return_value=loop), \
             patch("driver_turn.diagnose", return_value=[]), \
             patch.object(space, "idle", side_effect=idle):
            self.assertEqual(0, graph_goal.command_run(args))
        self.assertEqual([300], pauses)
        self.assertEqual(["done", "done"], [row["status"] for row in book.tasks()])
        self.assertEqual(4, len(calls))
        pauses = [row for row in space.events() if row["kind"] == "pause"]
        self.assertEqual(1, len(pauses))
        self.assertEqual({"T1", "T2"}, set(pauses[0]["tasks"]))


if __name__ == "__main__":
    unittest.main()
