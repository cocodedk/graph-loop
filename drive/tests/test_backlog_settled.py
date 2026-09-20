"""A need on a sliced or dropped card must not wait for ever.

`slice_task` never sets a parent to done, and `ready` counted only done, so a
card waiting on a sliced parent could never start. Two cards sat behind one all
night on 2026-08-31, and a third behind a card that had been dropped.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog import Backlog

EXPECTED_TESTS = 6


def book(*rows: dict) -> Backlog:
    path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"tasks": list(rows)}))
    return Backlog(path)


def card(task_id: str, status: str = "todo", needs=()) -> dict:
    return {"id": task_id, "status": status, "needs": list(needs), "files": [], "gate": "true"}


class ANeedThatCanBeSatisfied(unittest.TestCase):
    def test_a_sliced_parent_settles_once_its_pieces_are_done(self):
        rows = book(card("T4", "sliced", ["T4.a", "T4.b"]), card("T4.a", "done"),
                    card("T4.b", "done"), card("T5", needs=["T4"]))
        self.assertIn("T5", [row["id"] for row in rows.ready()])

    def test_a_sliced_parent_with_an_unfinished_piece_still_blocks(self):
        rows = book(card("T4", "sliced", ["T4.a", "T4.b"]), card("T4.a", "done"),
                    card("T4.b"), card("T5", needs=["T4"]))
        self.assertNotIn("T5", [row["id"] for row in rows.ready()])

    def test_a_slice_of_a_slice_settles_when_its_own_pieces_do(self):
        rows = book(card("T4", "sliced", ["T4.a"]), card("T4.a", "sliced", ["T4.a1"]),
                    card("T4.a1", "done"), card("T5", needs=["T4"]))
        self.assertIn("T5", [row["id"] for row in rows.ready()])

    def test_a_dropped_card_settles_so_what_followed_it_can_run(self):
        rows = book(card("T7", "dropped"), card("T8", needs=["T7"]))
        self.assertIn("T8", [row["id"] for row in rows.ready()])

    def test_a_piece_the_backlog_does_not_hold_never_settles_its_parent(self):
        """Ignoring an unknown piece would settle a parent on work nobody wrote."""
        rows = book(card("T4", "sliced", ["T4.a", "T4.ghost"]), card("T4.a", "done"),
                    card("T5", needs=["T4"]))
        self.assertNotIn("T5", [row["id"] for row in rows.ready()])

    def test_a_refused_card_still_blocks_what_waits_on_it(self):
        rows = book(card("T7", "refused_contract"), card("T8", needs=["T7"]))
        self.assertNotIn("T8", [row["id"] for row in rows.ready()])


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
