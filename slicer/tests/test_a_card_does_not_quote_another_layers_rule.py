"""A card quoted a rule from the wrong layer back at the planner.

The drive loop's REPLAN rewrites one card, may not add a file, and records its
refusals on the card — "it may narrow the grant, never widen it". The slicer is
shown the whole card, read that as its own law, and answered `needs_person`,
which `repair.REPAIRABLE` excludes by design, so nothing could challenge it.

It is false at this layer: only a ONE-LEAF rewrite may not add a file
(`contracts.py`), and minutes earlier the same campaign had published a
two-atom molecule whose stage 1 granted a file its target never held. The card
was pinned by a sentence that was true where it was written and false where it
was read (2026-09-18).
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import asking
from tree import publish

import slicer

EXPECTED_TESTS = 1


def molecule() -> dict:
    return {"name": "large", "source": ["specs/greeting.md:1"], "goal": "return a greeting",
            "why": "the function is absent", "needs": [], "atoms": [], "files": ["app.py"],
            "gate": "set -e -o pipefail\nfalse", "done_when": "the greeting test passes",
            "may_add_files": True}


class TheRuleShownIsThisLayersOwn(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.repo = self.root / "repo"
        self.backlog, self.specs = self.repo / "backlog", self.repo / "specs"
        self.backlog.mkdir(parents=True)
        self.specs.mkdir()
        (self.specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")

    def test_the_prompt_says_a_prerequisite_atom_may_grant_a_new_file(self):
        parent = molecule()
        parent["name"] = "large"
        publish(self.backlog, parent)
        slicer.Backlog(self.backlog).set_status(
            "large", "needs_slice", triage="work", refused_why="too broad",
            replan_history=["it may narrow the grant, never widen it"])
        rows = slicer.Backlog(self.backlog).tasks()
        target = next(row for row in rows if row["id"] == "large")
        said = asking.prompt(self.repo, [self.specs], rows, target, [])
        self.assertIn("prerequisite atom", said)
        self.assertIn("replan_history", said)          # named, so it cannot be mistaken for law


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
