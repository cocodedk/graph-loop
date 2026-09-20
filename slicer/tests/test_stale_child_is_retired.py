"""A stale child publication is retired once, not refused for ever.

Recovery found the same stale child every run — the parent was rewritten after
the child landed, so `roll_forward` refused it as `CardMoved`, which costs
nothing and changes nothing, and the next turn asked the same question again.
The parent stayed the slicer's for ever and nothing ever planned it (astra's
round-4 finding 9).

The retirement preserves what was paid for: the folder is renamed out of the
reader's way, whole, and the parent is free to be sliced again.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
GRAPH_LIB = HERE.parent / "graph" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GRAPH_LIB))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog  # type: ignore[import-not-found]
from test_tree import task
from tree import publish, recover

import slicer

EXPECTED_TESTS = 3


def staled(child: str = "small", *, keep_waits: bool = False) -> tuple[pathlib.Path, Backlog]:
    """A campaign whose child landed, whose parent's own write did not, and
    whose parent was rewritten after that: the child can never be finished."""
    repo = pathlib.Path(tempfile.mkdtemp())
    backlog, specs = repo / "backlog", repo / "specs"
    backlog.mkdir()
    specs.mkdir()
    (specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")
    book = Backlog(backlog)
    publish(backlog, task("large"))
    publish(backlog, task(child), "large")             # the child landed...
    fields: dict = {} if keep_waits else {"needs": []}  # ...and the parent's write did not
    book.set_status("large", "needs_slice", triage="work", refused_why="too broad", **fields)
    book.note("large", goal="build large, narrowed by hand")   # nobody planned for this
    return repo, book


def planned(repo: pathlib.Path):
    """One slicer run over that campaign, with the planner standing still."""
    with mock.patch.object(slicer, "ask", return_value=types.SimpleNamespace(
            ok=False, why="no planner in this test", text="")) as ask:
        slicer.main(["--repo", str(repo), "--backlog", str(repo / "backlog"),
                     "--target", "large", "--source", "specs/greeting.md"])
    return ask


class StaleChildRetiredTest(unittest.TestCase):
    def test_a_stale_child_is_retired_and_its_parent_is_planned_again(self):
        repo, book = staled()
        backlog = repo / "backlog"

        ask = planned(repo)

        ask.assert_called_once()                       # recovery let the planning happen
        self.assertIsNone(book.task("small"))          # the stale child is out of the way
        self.assertEqual("needs_slice", book.task("large")["status"])
        self.assertEqual([], book.task("large")["needs"] or [])
        [retired] = [path for path in backlog.iterdir() if path.name.startswith(".stale-small")]
        self.assertTrue((retired / "molecule.md").exists())   # and it is kept, whole

    def test_the_parent_stops_waiting_for_the_child_that_was_retired(self):
        """The publish that settled the parent wrote the wait, and re-parking
        the card kept it: retiring the child left the parent waiting for a card
        that no longer exists, and the replacement inherited that wait (Codex on
        7f16068a, finding 4)."""
        repo, book = staled(keep_waits=True)
        backlog = repo / "backlog"
        self.assertEqual(["small"], book.task("large")["needs"])

        self.assertEqual("", recover(backlog, "large")[0])       # retired, not finished

        self.assertEqual([], book.task("large")["needs"] or [])
        publish(backlog, task("fresh"), "large")
        self.assertEqual([], book.task("fresh")["needs"] or [])

    def test_the_planner_is_never_shown_the_card_that_was_just_retired(self):
        """The rows were read before recovery, so the prompt still held the
        retired child and the planner planned around a card that is gone
        (an independent review, finding 5)."""
        repo, _book = staled("brokerreplay")

        ask = planned(repo)

        self.assertNotIn("brokerreplay", ask.call_args[0][0])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
