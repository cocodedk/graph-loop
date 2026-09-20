"""A recorded cut check leaves its event and both artifacts, and changes nothing."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import cut_record
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from workspace import Workspace  # type: ignore[import-not-found]

STATE = {"molecule": "m1"}
QUESTIONS = ["one?", "two?"]


class CutRecordTest(unittest.TestCase):
    def setUp(self):
        self.space = Workspace(tempfile.mkdtemp())

    def asked(self):
        return [row for row in self.space.events() if row["kind"] == "cut_asked"]

    def names(self):
        return [row["name"] for row in self.space.events() if row["kind"] == "artifact"]

    def test_ok_answer_passes_through_and_is_recorded(self):
        answer = types.SimpleNamespace(ok=True, answers=[1, 2], cost=0.5, seconds=2.0, why="")
        got = cut_record.recording(self.space, lambda s, q: answer)(STATE, QUESTIONS)
        self.assertIs(got, answer)
        (row,) = self.asked()
        self.assertEqual((row["ok"], row["cost"], row["seconds"], row["questions"], row["task"]),
                         (True, 0.5, 2.0, 2, "cut-check"))
        self.assertEqual(self.names(), ["cut-request", "cut-answer"])

    def test_not_ok_carries_its_why_and_missing_fields_still_record(self):
        answer = types.SimpleNamespace(ok=False, why="usage limit")
        got = cut_record.recording(self.space, lambda s, q: answer, label="x")(STATE, QUESTIONS)
        self.assertIs(got, answer)
        (row,) = self.asked()
        self.assertEqual((row["ok"], row["why"], row["cost"], row["task"]),
                         (False, "usage limit", None, "x"))
        self.assertEqual(self.names(), ["cut-request", "cut-answer"])

    def test_a_raising_ask_is_recorded_and_raised_again(self):
        def boom(state, questions):
            raise ValueError("no route")

        with self.assertRaises(ValueError):
            cut_record.recording(self.space, boom)(STATE, QUESTIONS)
        (row,) = self.asked()
        self.assertFalse(row["ok"])
        self.assertIn("ValueError", row["why"])
        self.assertIn("no route", row["why"])
        self.assertEqual(self.names(), ["cut-request", "cut-answer"])


if __name__ == "__main__":
    unittest.main()
