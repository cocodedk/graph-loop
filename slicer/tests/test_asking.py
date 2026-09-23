"""The planner's prompt carries the wall's whole ancestry as prior art."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asking
import asking_lists  # the ceiling lives with the listings it bounds
import contracts
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from tree import publish

import slicer

EXPECTED_TESTS = 10


def rig():
    repo = pathlib.Path(tempfile.mkdtemp())
    (repo / "specs").mkdir()
    source = repo / "specs" / "a.md"
    source.write_text("## Goal\n", "utf-8")
    return repo, source


class AncestryTest(unittest.TestCase):
    def test_the_prompt_keeps_work_in_the_loop_and_asks_for_person_only_inputs_first(self):
        question = asking.prompt(pathlib.Path.cwd(), [], [])
        for rule in (
            "A plan never gives work to a person.",
            "Work that a person judges is still the loop's to build",
            'its gate is "it builds and every existing test stays green"',
            "the person accepts the result at the end",
            "judgement is never a reason to cut no card",
            "What only a person can supply (a file the loop cannot fetch, a credential, a decision)",
            "is asked before any card is cut",
            "answer NEEDS_PERSON first, naming it, and plan nothing further until it is answered",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, question)

    def test_a_walls_ancestors_appear_in_the_prompt(self):
        repo, source = rig()
        rows = [{"id": "P0", "goal": "the grandparent plan that failed", "sliced_from": ""},
                {"id": "T1", "goal": "the wall", "sliced_from": "P0"}]
        question = asking.prompt(repo, [source], rows, rows[1])
        self.assertIn("the grandparent plan that failed", question)
        self.assertIn("Ancestors of the target", question)
        self.assertIn("Never pin EXPECTED to a literal, to len(...), or to a value read from HEAD", question)

    def test_a_source_gap_prompt_names_no_ancestors(self):
        repo, source = rig()
        question = asking.prompt(repo, [source], [], None)
        self.assertIn("Ancestors of the target, nearest first (prior art, never to repeat):\nnone",
                      question)


class AnswerShapeTest(unittest.TestCase):
    def test_prompt_skeleton_passes_contract_key_checks(self):
        repo, source = rig()
        question = asking.prompt(repo, [source], [])
        self.assertEqual(1, len(contracts.FENCE.findall(question)))
        answer = contracts.mapping(question)
        self.assertEqual("MOLECULE", answer["result"])
        contracts._keys(answer, contracts.TOP, contracts.TOP, "answer")
        made = answer["molecule"]
        contracts._keys(made, contracts.BASE | {"note"}, contracts.BASE, "molecule")
        self.assertEqual(1, len(made["atoms"]))
        atom = made["atoms"][0]
        contracts._keys(atom, contracts.ATOM, contracts.REQUIRED | {"name", "stage"}, "atom")
        self.assertEqual(contracts.ATOM, set(atom))


class CoveredWorkTest(unittest.TestCase):
    def test_existing_goals_and_ids_reach_the_gap_planner(self):
        repo, source = rig()
        rows = [{"id": "T1", "status": "done", "files": ["app.py"],
                 "goal": "already-covered greeting work",
                 "gate": "grep -q greeting app.py"}]
        question = asking.prompt(repo, [source], rows, None)
        self.assertIn("T1 [done] files=app.py — already-covered greeting work", question)
        # the compact index deliberately drops gate text; only id, status,
        # files and the goal's first line reach the planner per existing row
        self.assertNotIn("grep -q greeting app.py", question)


class IndexCoverageTest(unittest.TestCase):
    def test_every_existing_molecule_reaches_the_planner(self):
        # each row also carries a fat gate string: full-YAML row dumps used to
        # blow the old 60,000-char cut on content the compact index never
        # shows, so most ids and goals below never reached the planner.
        repo, source = rig()
        rows = [{"id": f"T{i:03d}", "status": "done", "files": [f"f{i:03d}.py"],
                 "goal": f"distinct goal line number {i:03d}",
                 "gate": "g" * 1000} for i in range(200)]
        question = asking.prompt(repo, [source], rows, None)
        for i in range(200):
            self.assertIn(f"T{i:03d}", question)
            self.assertIn(f"distinct goal line number {i:03d}", question)


class BudgetTest(unittest.TestCase):
    def test_a_queue_past_the_budget_refuses_loudly(self):
        repo, source = rig()
        rows = [{"id": f"T{i}", "status": "done", "files": [],
                 "goal": "goal text padded to add length " * 3} for i in range(30)]
        with mock.patch.object(asking_lists, "PROMPT_BUDGET", 2_000), self.assertRaises(ValueError) as ctx:
            asking.prompt(repo, [source], rows, None)
        self.assertIn("too large", str(ctx.exception))


class CoverageBudgetScopeTest(unittest.TestCase):
    def test_the_budget_covers_only_the_index_not_the_whole_prompt(self):
        # today's real spec text runs ~1.25 MB; a coverage review must not
        # refuse over source size when the compact index itself is small
        repo, _source = rig()
        big_source = repo / "specs" / "big.md"
        big_source.write_text("x" * 2_000_000, "utf-8")
        rows = [{"id": f"T{i}", "status": "done", "files": [],
                 "goal": f"goal {i}"} for i in range(132)]
        question = asking.coverage_prompt(repo, [big_source], rows)
        self.assertIn("x" * 2_000_000, question)
        # but an index that is itself too large to plan against still refuses
        with mock.patch.object(asking_lists, "PROMPT_BUDGET", 200), self.assertRaises(ValueError) as ctx:
            asking.coverage_prompt(repo, [big_source], rows)
        self.assertIn("too large", str(ctx.exception))


class FullFirstLineTest(unittest.TestCase):
    def test_a_long_goal_first_line_is_never_cut(self):
        repo, source = rig()
        first_line = "g" * 400
        rows = [{"id": "T1", "status": "done", "files": [],
                 "goal": first_line + "\nsecond line ignored"}]
        question = asking.prompt(repo, [source], rows, None)
        self.assertIn(first_line, question)


class NoGapTraceOrderTest(unittest.TestCase):
    def test_a_refused_coverage_prompt_records_no_review_call(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        backlog = repo / "backlog"; backlog.mkdir()
        (repo / "specs").mkdir()
        source = repo / "specs" / "a.md"
        source.write_text("## Goal\n", "utf-8")
        publish(backlog, {
            "name": "greeting", "source": ["specs/a.md:1"], "goal": "return a greeting",
            "why": "missing", "needs": [], "atoms": [], "files": ["app.py"], "gate": "false",
            "done_when": "the greeting test passes"})
        answer = yaml.safe_dump({"result": "NO_GAP", "reason": "nothing left", "molecule": None})
        never_called = lambda _question: self.fail("reviewer reached: coverage_prompt should refuse first")
        with mock.patch.object(asking_lists, "PROMPT_BUDGET", 1):
            state, detail = slicer.run_answer(answer, repo=repo, backlog=backlog,
                                              sources=[source], reviewer=never_called)
        self.assertEqual("planning_refused", state)
        self.assertIn("too large", detail)
        steps = [json.loads(line)["step"]
                 for line in (backlog / ".slicer-trace.jsonl").read_text().splitlines()]
        self.assertNotIn("coverage_review_call", steps)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
