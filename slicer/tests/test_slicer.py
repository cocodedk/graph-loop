"""The standalone command repairs bad answers and remembers covered sources."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import slicer_state
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from intelligence import Reply
from tree import publish

import slicer

EXPECTED_TESTS = 10


def molecule() -> str:
    return yaml.safe_dump({
        "result": "MOLECULE", "reason": "one missing function", "molecule": {
            "name": "greeting", "source": ["specs/greeting.md:1"],
            "goal": "return a greeting", "why": "the function is absent", "needs": [],
            "atoms": [], "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
            "done_when": "the greeting test passes", "may_add_files": True}},
        sort_keys=False)


class Command(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.repo = self.root / "repo"
        self.backlog, self.specs = self.repo / "backlog", self.repo / "specs"
        self.backlog.mkdir(parents=True)
        self.specs.mkdir()
        self.source = self.specs / "greeting.md"
        self.source.write_text("## Goal\nReturn a greeting.\n", "utf-8")

    def test_an_accepted_digest_is_reused_until_a_source_changes(self):
        slicer_state.close(self.backlog, [self.source], "accepted", self.repo, [])
        self.assertTrue(slicer_state.covered(self.backlog, [self.source], self.repo, []))
        self.source.write_text("## Goal\nReturn two greetings.\n", "utf-8")
        self.assertFalse(slicer_state.covered(self.backlog, [self.source], self.repo, []))
        self.assertFalse((self.backlog / ".slicer-state.yaml").exists())

    def test_a_bad_planner_answer_gets_a_repair_round(self):
        replies = [Reply(True, "{}"), Reply(True, molecule())]
        with mock.patch.object(slicer, "ask", side_effect=replies) as ask:
            result = slicer.main(["--repo", str(self.repo), "--backlog", str(self.backlog),
                                  "--source", "specs"])
        self.assertEqual(0, result)
        self.assertEqual(2, ask.call_count)
        self.assertIn("validator refused", ask.call_args.args[0])

    def test_an_external_source_is_refused_before_a_model_call(self):
        outside = self.root / "outside.md"
        outside.write_text("not approved\n", "utf-8")
        with mock.patch.object(slicer, "ask") as ask:
            result = slicer.main(["--repo", str(self.repo), "--backlog", str(self.backlog),
                                  "--source", str(outside)])
        self.assertEqual(2, result)
        ask.assert_not_called()

    def test_the_prompt_says_a_stage_is_a_number(self):
        question = slicer.prompt(self.repo, [self.source], [])
        self.assertIn("positive integer such as 1, never a word", question)
        self.assertIn("unequal to every existing task id", question)
        self.assertIn("never code or failure evidence", question)
        self.assertIn("try to pass each gate without doing its work", question)
        self.assertIn("Never invent a required method", question)
        self.assertIn("the gate cannot observe, or a shape nothing here declares, "
                      "answer NEEDS_PERSON", question)
        # a method it cannot observe was all this reached, so a card could invent a
        # page format and the gate would prove the code matched the invention
        self.assertIn("never invent the SHAPE of data from outside this repository", question)
        self.assertIn("`src/main/Link.java:parseLink`", question)   # the form to write
        self.assertIn("A bare path is not a name and neither is `creates: [result.txt]`", question)

    def test_restart_rolls_a_published_child_forward_without_a_model(self):
        parent = {"name": "large", "source": ["specs/greeting.md:1"],
                  "goal": "large work", "why": "missing", "needs": [], "atoms": [],
                  "files": ["app.py"], "gate": "set -e -o pipefail\nfalse", "done_when": "proof"}
        child = {**parent, "name": "small", "goal": "small work"}
        publish(self.backlog, parent)
        publish(self.backlog, child, "large")
        slicer.Backlog(self.backlog).set_status("large", "needs_slice", needs=[], triage="work")
        with mock.patch.object(slicer, "ask") as ask:
            result = slicer.main(["--repo", str(self.repo), "--backlog", str(self.backlog),
                                  "--source", "specs", "--target", "large"])
        self.assertEqual(0, result)
        ask.assert_not_called()
        self.assertEqual("sliced", slicer.Backlog(self.backlog).task("large")["status"])

    def test_a_runnable_target_is_refused_before_a_model_call(self):
        parent = yaml.safe_load(molecule())["molecule"]
        parent["name"] = "large"
        publish(self.backlog, parent)
        with mock.patch.object(slicer, "ask") as ask:
            result = slicer.main(["--repo", str(self.repo), "--backlog", str(self.backlog),
                                  "--source", "specs", "--target", "large"])
        self.assertEqual(2, result)
        ask.assert_not_called()

    def test_an_independent_progress_refusal_publishes_nothing(self):
        parent = yaml.safe_load(molecule())["molecule"]
        parent["name"] = "large"
        publish(self.backlog, parent)
        slicer.Backlog(self.backlog).set_status("large", "needs_slice",
                                                refused_why="the gate is too broad", triage="work")
        child = yaml.safe_load(molecule())
        child["molecule"].update(name="smaller", goal="narrow greeting")
        state, why = slicer.run_answer(yaml.safe_dump(child), repo=self.repo,
                                       backlog=self.backlog, sources=[self.specs],
                                       target_id="large",
                                       reviewer=lambda prompt: Reply(False, why="same work"))
        self.assertEqual(("progress_refused", "same work"), (state, why))
        self.assertFalse((self.backlog / "smaller").exists())
        self.assertEqual("needs_slice", slicer.Backlog(self.backlog).task("large")["status"])

    def test_an_independent_refusal_gets_a_repair_round_like_a_bad_shape(self):
        """The reviewer names what is wrong in words the planner can act on,
        and the command threw them away: only the validator's refusals were fed
        back, so one review refusal ended the turn (2026-09-18)."""
        parent = yaml.safe_load(molecule())["molecule"]
        parent["name"] = "large"
        publish(self.backlog, parent)
        slicer.Backlog(self.backlog).set_status("large", "needs_slice",
                                                refused_why="too broad", triage="work")
        child = yaml.safe_load(molecule())
        child["molecule"].update(name="smaller", goal="narrow greeting")
        answer = yaml.safe_dump(child)
        verdicts = [Reply(False, why="it repeats the parent's own work"), Reply(True, "ok")]
        with mock.patch.object(slicer, "ask", side_effect=[Reply(True, answer)] * 2) as ask, \
                mock.patch("slicer_answer.review", side_effect=verdicts):
            result = slicer.main(["--repo", str(self.repo), "--backlog", str(self.backlog),
                                  "--source", "specs", "--target", "large"])
        self.assertEqual(0, result)
        self.assertEqual(2, ask.call_count)
        self.assertIn("it repeats the parent's own work", ask.call_args.args[0])

    def test_a_review_outage_is_not_a_refusal(self):
        # nobody judged anything: the state must say so, or the caller
        # spends the target's slice-failure budget on a provider outage
        parent = yaml.safe_load(molecule())["molecule"]
        parent["name"] = "large"
        publish(self.backlog, parent)
        slicer.Backlog(self.backlog).set_status("large", "needs_slice",
                                                refused_why="too broad", triage="work")
        child = yaml.safe_load(molecule())
        child["molecule"].update(name="smaller", goal="narrow greeting")
        down = lambda prompt: Reply(False, why="the review did not happen (auth)", down=True)
        state, _why = slicer.run_answer(yaml.safe_dump(child), repo=self.repo,
                                        backlog=self.backlog, sources=[self.specs],
                                        target_id="large", reviewer=down)
        self.assertEqual("review_unavailable", state)
        self.assertFalse((self.backlog / "smaller").exists())


class TraceTest(unittest.TestCase):
    def test_every_step_of_a_publish_lands_in_the_trace_in_order(self):
        # the owner's order: an overwhelm of logging — each step findable afterwards
        repo = pathlib.Path(tempfile.mkdtemp())
        backlog = repo / "backlog"; backlog.mkdir()
        (repo / "specs").mkdir()
        (repo / "specs" / "greeting.md").write_text("## Goal\nReturn a greeting.\n")
        answer = repo / "answer.yaml"
        answer.write_text(yaml.safe_dump({
            "result": "MOLECULE", "reason": "the function is absent", "molecule": {
                "name": "greeting", "source": ["specs/greeting.md:1"],
                "goal": "return one greeting", "why": "the function is absent",
                "needs": [], "atoms": [], "files": ["app.py"], "gate": "set -e -o pipefail\nfalse",
                "done_when": "the greeting test passes", "may_add_files": True}},
            sort_keys=False))
        rc = slicer.main(["--repo", str(repo), "--backlog", str(backlog),
                          "--source", "specs/greeting.md", "--answer", str(answer)])
        self.assertEqual(0, rc)
        steps = [json.loads(line)["step"]
                 for line in (backlog / ".slicer-trace.jsonl").read_text().splitlines()]
        wanted = ["start", "prompt_built", "answer_recorded", "validated", "published", "ended"]
        positions = [steps.index(w) for w in wanted]
        self.assertEqual(positions, sorted(positions), steps)


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
