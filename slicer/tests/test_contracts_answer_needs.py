"""Answer-local ids exist before publication; stages own sibling waits."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import tmp_root  # noqa: F401 — temporary repositories are removed at exit
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "slicer"))
sys.path.insert(0, str(ROOT / "graph" / "lib"))
from backlog import Backlog
from contract_task import _task
from contracts import validate
from intelligence import Reply
from tree import publish

import slicer


class AnswerNeedsTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        self.source = self.repo / "spec.md"
        self.source.write_text("Return a greeting.\n", "utf-8")
        self.atoms = [self.atom("schema", 1), self.atom("reader", 2)]
        self.answer = {"result": "MOLECULE", "reason": "missing greeting", "molecule": {
            "name": "greeting", "source": ["spec.md:1"], "goal": "return a greeting",
            "why": "missing", "needs": [], "atoms": self.atoms}}

    def atom(self, name, stage):
        return {"name": name, "stage": stage, "goal": "return a greeting",
                "files": [f"{name}.py"], "may_add_files": True,
                "gate": "set -e -o pipefail\nfalse", "done_when": "the gate passes"}

    def check(self, rows=()):
        return validate(self.answer, repo=self.repo, sources=[self.source], rows=list(rows))

    def test_sibling_need_is_dropped_and_the_published_stage_derives_it(self):
        self.atoms[1]["needs"] = ["greeting.schema"]
        made = self.check()["molecule"]
        self.assertEqual([], made["atoms"][1]["needs"])
        backlog = self.repo / "backlog"
        backlog.mkdir()
        publish(backlog, made)
        self.assertEqual(["greeting.schema"], Backlog(backlog).task("greeting.reader")["needs"])

    def test_stage_order_wins_over_an_explicit_forward_sibling_wait(self):
        self.atoms[0]["needs"] = ["greeting.reader"]
        self.check()
        self.assertEqual([], self.atoms[0]["needs"])

    def test_external_molecule_and_atom_needs_stay(self):
        self.atoms[1]["needs"] = ["other", "other.atom", "greeting.schema"]
        self.check(rows=[{"id": "other"}, {"id": "other.atom"}])
        self.assertEqual(["other", "other.atom"], self.atoms[1]["needs"])

    def test_answer_ids_are_known_even_before_their_cards_exist(self):
        # The leaf rule is independent of origin. The current closed answer
        # supplies one molecule; other molecules currently arrive via the backlog.
        leaf = self.atoms[1]
        leaf["needs"] = ["other", "other.atom", "greeting.schema"]
        _task(leaf, self.repo, {"other", "other.atom", "greeting.schema"},
              siblings={"greeting.schema"})
        self.assertEqual(["other", "other.atom"], leaf["needs"])

    def test_an_unknown_need_is_still_refused(self):
        for missing in ("absent", "greeting.absent"):
            with self.subTest(missing=missing):
                self.atoms[1]["needs"] = [missing]
                with self.assertRaisesRegex(ValueError, "task that does not exist"):
                    self.check()

    def test_an_atom_waiting_on_its_molecule_is_a_cycle_not_a_missing_task(self):
        self.atoms[0]["needs"] = ["greeting"]
        with self.assertRaisesRegex(ValueError, "circle"):
            self.check()

    def test_an_atom_is_not_its_own_sibling(self):
        self.atoms[0]["needs"] = ["greeting.schema"]
        with self.assertRaisesRegex(ValueError, "circle"):
            self.check()

    def test_colon_and_sibling_need_publish_on_the_first_planner_answer(self):
        self.atoms[1]["needs"] = ["greeting.schema"]
        text = yaml.safe_dump(self.answer, sort_keys=False).replace(
            "goal: return a greeting", "goal: AndroidFeedback(view: View) : Feedback present")
        backlog = self.repo / "backlog"
        backlog.mkdir()
        with mock.patch.object(slicer, "ask", return_value=Reply(True, text)) as ask:
            rc = slicer.main(["--repo", str(self.repo), "--backlog", str(backlog),
                              "--source", "spec.md"])
        self.assertEqual(0, rc)
        self.assertEqual(1, ask.call_count)
        self.assertEqual({"greeting", "greeting.schema", "greeting.reader"},
                         {row["id"] for row in Backlog(backlog).tasks()})

    def test_an_unrepaired_yaml_error_reaches_the_correction_prompt_verbatim(self):
        line = "reason: @" + "the original offending sentence " * 10
        backlog = self.repo / "backlog"
        backlog.mkdir()
        replies = [Reply(True, line + "\n"), Reply(True, yaml.safe_dump(self.answer))]
        with mock.patch.object(slicer, "ask", side_effect=replies) as ask:
            rc = slicer.main(["--repo", str(self.repo), "--backlog", str(backlog),
                              "--source", "spec.md"])
        self.assertEqual(0, rc)
        self.assertEqual(2, ask.call_count)
        self.assertIn("offending line 1:\n" + line, ask.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
