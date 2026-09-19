"""A hold raised while the planner runs stops the slicer after ONE call.

The publish-time check is the last chance, not the first: `validate` asserts
the wall before it, and that refusal is answered with a repair round — so a
person holding the card mid-plan bought two more paid planner calls before
anything noticed. The rig lives in `test_slicer`.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from intelligence import Reply
from test_slicer import molecule
from tree import publish

import slicer

EXPECTED_TESTS = 1


class HeldWhilePlanningTest(unittest.TestCase):
    def test_a_hold_raised_while_the_planner_ran_stops_after_one_call(self):
        root = pathlib.Path(tempfile.mkdtemp())
        repo = root / "repo"
        backlog, specs = repo / "backlog", repo / "specs"
        backlog.mkdir(parents=True)
        specs.mkdir()
        (specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")
        parent = yaml.safe_load(molecule())["molecule"]
        parent["name"] = "large"
        publish(backlog, parent)
        book = slicer.Backlog(backlog)
        book.set_status("large", "needs_slice", refused_why="too broad", triage="work")

        child = yaml.safe_load(molecule())
        child["molecule"].update(name="smaller", goal="narrow greeting")

        def hold_then_answer(question, where):
            book.note("large", blocked_by_human=True)     # a person, mid-plan
            return Reply(True, yaml.safe_dump(child))

        with mock.patch.object(slicer, "ask", side_effect=hold_then_answer) as ask:
            result = slicer.main(["--repo", str(repo), "--backlog", str(backlog),
                                  "--source", "specs", "--target", "large"])
        self.assertEqual(2, result)
        self.assertEqual(1, ask.call_count)              # not a repair round each
        self.assertTrue(book.task("large")["blocked_by_human"])
        self.assertEqual("needs_slice", book.task("large")["status"])
        self.assertFalse((backlog / "smaller").exists())


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
