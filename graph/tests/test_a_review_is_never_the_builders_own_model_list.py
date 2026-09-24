"""The claude rungs of the review belt are not the builder list.

They read `models.builders()` until 2026-09-18. The moment the builder list was
reordered to put the fast model first, a machine whose codex was unreachable
reviewed every change with the same model that wrote it — which is the one thing
a review exists to avoid (CLAUDE.md § Code: an independent reviewer, never the
builder). The first real campaign run hit it: with no codex installed there was
no way to review with a stronger model than the one that built, and a reviewer
had to be stood in by hand.
"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import models
import resources

EXPECTED_TESTS = 5


def claude_rungs() -> list[str]:
    return [one.model for one in resources.belt("review") if one.agent == "claude"]


class ReviewBeltTest(unittest.TestCase):
    def test_the_claude_reviewers_are_their_own_list(self):
        self.assertNotEqual(models.builders(), models.claude_reviewers())

    def test_no_claude_review_rung_leads_with_the_first_builder(self):
        """Leading with it is the failure: the first rung is what answers."""
        self.assertNotEqual(models.builders()[0], claude_rungs()[0])

    def test_the_list_is_a_line_of_data(self):
        with unittest.mock.patch.dict(os.environ,
                                      {"GRAPH_CLAUDE_REVIEWERS": "one, two"}):
            self.assertEqual(("one", "two"), models.claude_reviewers())

    def test_planning_uses_strong_models_even_with_a_builder_override(self):
        with unittest.mock.patch.dict(os.environ, {"GRAPH_BUILDERS": "fast-only"}), \
                unittest.mock.patch("accounts.available", return_value=["first", "second"]):
            self.assertEqual(
                [("claude", account, model)
                 for model in ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5")
                 for account in ("first", "second")],
                [(r.agent, r.account, r.model) for r in resources.belt("plan")])
            self.assertEqual(["fast-only", "fast-only"],
                             [r.model for r in resources.belt("build")])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
