"""The speccer writes only a closed, independently accepted source."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from intelligence import Reply
from slicer_state import record
from speccer import prompt, write_answer

EXPECTED_TESTS = 6


def answer(body: str = "# Greeting\n\n## Goal\nReturn a greeting.\n\n"
                         "## Acceptance\nThe greeting test passes.\n\n"
                         "## Boundaries\nNo network or live action.\n") -> str:
    return yaml.safe_dump({"result": "SPEC", "reason": "the goal needs a contract",
                           "spec": {"name": "greeting", "body": body}}, sort_keys=False)


class Speccing(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp()) / "specs"

    def test_an_accepted_spec_is_written_once(self):
        state, path = write_answer(answer(), goal="greet", spec_root=self.root,
                                   reviewer=lambda prompt: Reply(True, "accepted"))
        self.assertEqual("written", state)
        self.assertIn("## Acceptance", pathlib.Path(path).read_text("utf-8"))

    def test_a_spec_without_its_boundary_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Boundaries"):
            write_answer(answer("## Goal\nx\n## Acceptance\ny"), goal="greet",
                         spec_root=self.root, reviewer=lambda prompt: Reply(True))

    def test_an_independent_rejection_writes_nothing(self):
        state, why = write_answer(answer(), goal="greet", spec_root=self.root,
                                  reviewer=lambda prompt: Reply(False, why="invented fact"))
        self.assertEqual(("review_refused", "invented fact"), (state, why))
        self.assertFalse(self.root.exists())

    def test_needs_person_is_a_closed_non_write(self):
        text = yaml.safe_dump({"result": "NEEDS_PERSON", "reason": "goal is unclear",
                               "spec": None})
        state, why = write_answer(text, goal="greet", spec_root=self.root)
        self.assertEqual(("needs_person", "goal is unclear"), (state, why))

    def test_call_records_go_where_the_planner_will_not_read_them(self):
        """They used to land inside the repository the planner is told to read,
        so a retry found its own refused answer and reused it (2026-09-18)."""
        repo, campaign = self.root.parent, self.root.parent.parent / "campaign"
        record(campaign, "question", "answer", ".speccer-calls")
        self.assertTrue((campaign / ".speccer-calls" / "0001-answer.yaml").is_file())
        self.assertFalse((repo / ".speccer-calls").exists())
        self.assertFalse((self.root / ".speccer-calls").exists())

    def test_the_prompt_forbids_an_unobservable_method(self):
        self.assertIn("Do not add a required method", prompt("make it", self.root.parent))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
