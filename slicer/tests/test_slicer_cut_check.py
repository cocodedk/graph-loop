"""`run_answer` runs an optional checker between validation and review."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from typing import NamedTuple

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from intelligence import Reply

import slicer


class Result(NamedTuple):
    molecule: dict
    findings: list


def answer() -> dict:
    return {"result": "MOLECULE", "reason": "one missing function", "molecule": {
        "name": "greeting", "source": ["specs/greeting.md:1"],
        "goal": "return a greeting", "why": "the function is absent", "needs": [],
        "atoms": [], "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
        "done_when": "the greeting test passes", "may_add_files": True}}


class Checker(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        self.backlog, self.specs = self.repo / "backlog", self.repo / "specs"
        self.backlog.mkdir()
        self.specs.mkdir()
        (self.specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")
        self.reviewed: list = []

    def run_it(self, checker):
        return slicer.run_answer(yaml.safe_dump(answer()), repo=self.repo,
                                 backlog=self.backlog, sources=[self.specs],
                                 reviewer=self.reviewer, checker=checker)

    def reviewer(self, question):
        self.reviewed.append(question)
        return Reply(True, "ok")

    def cards(self) -> str:
        return "\n".join(p.read_text("utf-8") for p in self.backlog.rglob("*.md"))

    def test_findings_refuse_the_answer_before_review(self):
        checker = lambda molecule: Result(molecule, ["cut one is too small", "cut two too"])
        with self.assertRaisesRegex(ValueError, "cut one is too small; cut two too"):
            self.run_it(checker)
        self.assertEqual([], self.reviewed)
        self.assertEqual("", self.cards())

    def test_a_checker_that_is_falsy_still_runs(self):
        class Falsy:
            def __bool__(self):
                return False

            def __call__(self, molecule):
                return Result(molecule, ["reject this cut"])
        with self.assertRaisesRegex(ValueError, "reject this cut"):
            self.run_it(Falsy())
        self.assertEqual([], self.reviewed)

    def test_a_changed_molecule_is_validated_again_and_published(self):
        checker = lambda molecule: Result({**molecule, "goal": "return a friendly greeting"}, [])
        self.assertEqual(("published", "greeting"), self.run_it(checker))
        self.assertIn("friendly", self.cards())

    def test_a_changed_molecule_the_validator_refuses_raises(self):
        checker = lambda molecule: Result({**molecule, "files": "not a list"}, [])
        with self.assertRaises(ValueError):
            self.run_it(checker)
        self.assertEqual("", self.cards())

    def test_a_changed_molecule_returned_in_place_is_validated_again(self):
        def checker(molecule):
            molecule["files"] = "not a list"
            return Result(molecule, [])
        with self.assertRaises(ValueError):
            self.run_it(checker)
        self.assertEqual([], self.reviewed)
        self.assertEqual("", self.cards())

    def test_a_checker_that_raises_changes_nothing(self):
        def checker(molecule):
            raise RuntimeError("down")
        self.assertEqual(("published", "greeting"), self.run_it(checker))
        self.assertIn("return a greeting", self.cards())

    def test_a_checker_that_edits_then_raises_changes_nothing(self):
        def checker(molecule):
            molecule["goal"] = "return a friendly greeting"
            raise RuntimeError("down")
        self.assertEqual(("published", "greeting"), self.run_it(checker))
        self.assertIn("return a greeting", self.cards())
        self.assertNotIn("friendly", self.cards())

    def test_no_checker_publishes_as_before(self):
        self.assertEqual(("published", "greeting"), self.run_it(None))


if __name__ == "__main__":
    unittest.main()
