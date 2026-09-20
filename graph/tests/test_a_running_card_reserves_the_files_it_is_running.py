"""Which card a running id stands for, when the backlog holds that id twice.

A backlog can hold two rows with the same id — `startable` has a guard for
exactly that, and nothing in the loop rejects it on the way in. Everything that
RUNS a card reads it through `Backlog.task`, which answers with the FIRST row of
that id. The reservation that keeps another lane off its files has to answer
with the same row, or the loop reserves one card's paths while a lane edits
another's.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import frontier
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog

EXPECTED_TESTS = 3


def card(task_id: str, files: list[str]) -> dict:
    return {"id": task_id, "goal": "g", "status": "todo", "needs": [],
            "files": list(files), "gate": "true", "done_when": "x"}


# T1 twice, on different paths, and a second card on the first T1's path.
TWICE = [card("T1", ["shared.py"]), card("T1", ["other.py"]),
         card("T2", ["shared.py"])]


def book_of(rows: list[dict]) -> Backlog:
    path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
    path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": rows}),
                    "utf-8")
    return Backlog(path)


class ReservationTest(unittest.TestCase):
    def test_the_row_that_runs_is_the_row_that_reserves(self):
        # `Backlog.task` — what the lane, the keeper and the scope check all
        # read — answers with the first row. So must the reservation.
        book = book_of(TWICE)
        self.assertEqual(["shared.py"], book.task("T1")["files"])
        self.assertEqual([], [row["id"] for row in book.startable(running=["T1"])])

    def test_a_card_already_running_is_never_offered_a_second_lane(self):
        # Reading the LAST row reserves `other.py`, leaves `shared.py` free,
        # and offers T1 again while T1 is running: two lanes, one claim.
        self.assertEqual([], [row["id"] for row in frontier.startable(TWICE, ["T1"])])

    def test_one_id_still_gets_one_card_when_nothing_is_running(self):
        self.assertEqual(["T1", "T2"],
                         [row["id"] for row in frontier.startable(
                             [card("T1", ["a.py"]), card("T1", ["a.py"]),
                              card("T2", ["b.py"])])])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
