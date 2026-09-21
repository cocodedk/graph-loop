"""The whole loop, wired to the real review path.

`test_loop.py`'s fakes prove the loop's shape with a stub reviewer that
records nothing; this file proves that `graph_commands._real_review` — what
the running loop actually hands `Loop` as `review` — reaches the campaign
ledger for both reviews a task pays for, the same way a build's per-account
calls already do (lib/loop_steps.py).
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE))

import graph_commands
import real_calls
from loop import Loop
from providers import Outcome
from test_loop import Fakes, repo_with, task

EXPECTED_TESTS = 2


def fake_codex(binary, prompt, *, cwd="", effort="", attempt=None, **_settings):
    """Stands in at the subprocess boundary, the way
    `test_graph_commands.RealReviewLedgerTest` does — one accepted call,
    reported through whichever ledger callback `_real_review` bound."""
    if attempt:
        attempt("ok", "second", 0.4, 900, "fine")
    return Outcome("ok", verdict="ACCEPT",
                   text='{"review":"ACCEPT","accept":true,"findings":[],"observations":[]}')


class RealReviewLedgerTest(unittest.TestCase):
    def test_both_reviews_of_a_task_land_in_the_campaign_ledger(self):
        fakes = Fakes()
        root, book, space = repo_with(task())
        loop = Loop(repo=root, backlog=book, space=space, build=fakes.builder,
                    review=graph_commands._real_review)
        with unittest.mock.patch.object(real_calls, "codex", fake_codex):
            out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        rows = [row for row in space.events()
                if row.get("kind") == "attempt" and row.get("account") == "second"]
        self.assertEqual([("T1", "review"), ("T1", "review")],
                         [(row["task"], row.get("purpose")) for row in rows])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
