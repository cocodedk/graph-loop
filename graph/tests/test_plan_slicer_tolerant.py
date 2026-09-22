"""A repaired answer lands cards; a later refusal keeps their count and files."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import tmp_root  # noqa: F401 — temporary repositories are removed at exit

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "graph" / "lib"))
sys.path.insert(0, str(ROOT / "slicer"))
import plan_phase
from backlog import Backlog
from slicer_answer import run_answer
from workspace import Workspace

ANSWER = """result: MOLECULE
reason: the feedback is missing
molecule:
  name: feedback
  source: [spec.md:1]
  goal: AndroidFeedback(view: View) : Feedback present
  why: feedback is missing
  needs: []
  atoms:
    - name: schema
      stage: 1
      goal: define feedback
      files: [schema.py]
      may_add_files: true
      gate: |
        set -e -o pipefail
        false
      done_when: the gate passes
    - name: reader
      stage: 2
      goal: read feedback
      files: [reader.py]
      may_add_files: true
      needs: [feedback.schema]
      gate: |
        set -e -o pipefail
        false
      done_when: the gate passes
"""


class PlanSlicerTolerantTest(unittest.TestCase):
    def test_the_plan_counts_published_cards_and_keeps_them_after_a_refusal(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        source = repo / "spec.md"
        source.write_text("Feedback is present.\n", "utf-8")
        backlog = repo / "backlog"
        backlog.mkdir()
        book, space = Backlog(backlog), Workspace(repo / "campaign")
        replies = iter([ANSWER, ANSWER.replace("feedback", "missing").replace(
            "needs: [missing.schema]", "needs: [unknown]")])
        refusals = []

        def slice_once(book, space):
            try:
                run_answer(next(replies), repo=repo, backlog=book.path, sources=[source])
            except ValueError as error:
                refusals.append(str(error))

        with mock.patch.object(plan_phase, "slice_pending", side_effect=slice_once) as call:
            added = plan_phase.plan(book, space)
        self.assertEqual(3, added)
        self.assertEqual(2, call.call_count)
        self.assertEqual(["an atom needs a task that does not exist"], refusals)
        self.assertEqual({"feedback", "feedback.schema", "feedback.reader"},
                         {row["id"] for row in book.tasks()})
        planned = [event for event in space.events() if event["kind"] == "planned"]
        self.assertEqual([["feedback", "feedback.reader", "feedback.schema"]],
                         [event["added"] for event in planned])
        self.assertFalse((backlog / "missing").exists())


if __name__ == "__main__":
    unittest.main()
