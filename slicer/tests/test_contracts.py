"""Closed slicer answers are checked before any backlog file changes."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from contracts import mapping, validate

EXPECTED_TESTS = 19


class Contracts(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "specs").mkdir()
        self.source = self.repo / "specs" / "greeting.md"
        self.source.write_text("# Greeting\nA greeting is returned.\n", "utf-8")
        (self.repo / "existing.py").write_text("present = True\n", "utf-8")
        (self.repo / "app.py").write_text("present = True\n", "utf-8")
        (self.repo / "reader.py").write_text("present = True\n", "utf-8")

    def atom(self, **changes) -> dict:
        body = {"name": "greeting", "source": ["specs/greeting.md:2"],
                "goal": "return one greeting", "why": "the function is absent",
                "needs": [], "atoms": [], "files": ["app.py"],
                "gate": "set -e -o pipefail\npython3 -m unittest test_app.py",
                "done_when": "the greeting test passes"}
        body.update(changes)
        return {"result": "MOLECULE", "reason": "one gap", "molecule": body}

    def check(self, answer: dict, target: dict | None = None,
              rows: list[dict] | None = None) -> dict:
        return validate(answer, repo=self.repo, sources=[self.repo / "specs"],
                        rows=rows if rows is not None else ([target] if target else []),
                        target=target)

    def test_a_molecule_of_one_has_one_complete_contract(self):
        self.assertEqual("MOLECULE", self.check(self.atom())["result"])

    def test_a_molecule_with_atoms_may_carry_a_note(self):
        # the prompt asks for file boundaries in `note`; refusing it at the
        # molecule level burned the round that held T26.observation.read
        answer = self.atom(note="app.py is this molecule's boundary", atoms=[
            {"name": "one", "stage": 1, "goal": "g", "files": ["app.py"],
             "gate": "set -e -o pipefail\nfalse", "done_when": "proof"}])
        answer["molecule"] = {key: value for key, value in answer["molecule"].items()
                              if key not in ("files", "gate", "done_when")}
        self.assertEqual("MOLECULE", self.check(answer)["result"])

    def test_a_parent_note_that_is_not_text_is_refused(self):
        answer = self.atom(note={"boundary": "app.py"}, atoms=[
            {"name": "one", "stage": 1, "goal": "g", "files": ["app.py"],
             "gate": "set -e -o pipefail\nfalse", "done_when": "proof"}])
        answer["molecule"] = {key: value for key, value in answer["molecule"].items()
                              if key not in ("files", "gate", "done_when")}
        with self.assertRaises(ValueError) as caught:
            self.check(answer)
        self.assertIn("note must be text", str(caught.exception))

    def test_the_top_shape_is_closed(self):
        with self.assertRaisesRegex(ValueError, "keys are closed"):
            self.check({**self.atom(), "ignored": "still decides"})

    def test_a_path_cannot_escape_the_repository(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.check(self.atom(files=["../outside.py"]))

    def test_a_lower_stage_may_create_a_name_for_a_later_one(self):
        first = self.atom(goal="make it", files=["app.py"], creates=["app.py:thing"])
        second = self.atom(goal="read it", files=["reader.py"], uses=["app.py:thing"])
        made = self.atom(atoms=[{**first["molecule"], "name": "schema", "stage": 1},
                                {**second["molecule"], "name": "reader", "stage": 2}])
        for key in ("files", "gate", "done_when"):
            made["molecule"].pop(key)
        for atom in made["molecule"]["atoms"]:
            for key in ("source", "why", "atoms"):
                atom.pop(key, None)
        self.assertEqual("MOLECULE", self.check(made)["result"])

    def test_a_parallel_atom_does_not_license_its_sibling(self):
        made = self.atom(atoms=[
            {"name": "schema", "stage": 1, "goal": "make it", "files": ["app.py"],
             "gate": "set -e -o pipefail\nfalse", "done_when": "made", "creates": ["app.py:thing"]},
            {"name": "reader", "stage": 1, "goal": "read it", "files": ["reader.py"],
             "gate": "set -e -o pipefail\nfalse", "done_when": "read", "uses": ["app.py:thing"]}])
        for key in ("files", "gate", "done_when"):
            made["molecule"].pop(key)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.check(made)

    def test_a_new_id_cannot_reset_the_same_failed_contract(self):
        target = {"id": "old", **{key: self.atom()["molecule"][key]
                                    for key in ("goal", "files", "gate", "done_when")},
                  "status": "needs_slice", "triage": "work"}
        with self.assertRaisesRegex(ValueError, "repeats"):
            self.check(self.atom(name="smaller"), target)

    def test_no_gap_cannot_hide_an_unresolved_target(self):
        target = {"id": "old", "goal": "work", "files": ["app.py"],
                  "gate": "set -e -o pipefail\nfalse", "done_when": "proof", "status": "needs_slice",
                  "triage": "work"}
        answer = {"result": "NO_GAP", "reason": "nothing left", "molecule": None}
        with self.assertRaisesRegex(ValueError, "unresolved target"):
            self.check(answer, target)

    def test_a_new_id_cannot_reset_a_grandparent_contract(self):
        ancestor = {"id": "old", **{key: self.atom()["molecule"][key]
                                      for key in ("goal", "files", "gate", "done_when")}}
        target = {"id": "smaller", "sliced_from": "old", "goal": "narrow work",
                  "files": ["app.py"], "gate": "set -e -o pipefail\nfalse", "done_when": "narrow proof",
                  "status": "needs_slice", "triage": "work"}
        with self.assertRaisesRegex(ValueError, "ancestor"):
            self.check(self.atom(name="smallest"), target, [ancestor, target])

    def test_a_source_anchor_is_not_optional(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            self.check(self.atom(source=[]))

    def test_code_work_cannot_smuggle_a_live_helper(self):
        with self.assertRaisesRegex(ValueError, "helper verbs"):
            self.check(self.atom(helper_verbs=["journal"]))

    def test_a_new_file_requires_the_write_capability(self):
        with self.assertRaisesRegex(ValueError, "may_add_files"):
            self.check(self.atom(files=["new.py"]))
        self.assertEqual("MOLECULE", self.check(
            self.atom(files=["new.py"], may_add_files=True))["result"])

    def test_text_cannot_grant_a_boolean_capability(self):
        with self.assertRaisesRegex(ValueError, "not text"):
            self.check(self.atom(may_add_files="false"))

    def test_only_an_unheld_code_wall_can_be_a_target(self):
        base = {"id": "old", "goal": "work", "files": ["app.py"],
                "gate": "set -e -o pipefail\nfalse", "done_when": "proof"}
        for change in ({"status": "todo", "triage": "work"},
                       {"status": "needs_slice", "triage": "work",
                        "blocked_by_human": True},
                       {"status": "needs_slice", "triage": "work",
                        "gate_has_side_effects": True},
                       {"status": "needs_slice", "triage": "harness"},
                       {"status": "needs_slice"}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "slice|wall"):
                self.check(self.atom(name="smaller"), {**base, **change})

    def test_the_standalone_slicer_cannot_author_live_work(self):
        with self.assertRaisesRegex(ValueError, "CODE atoms only"):
            self.check(self.atom(files=[]))

    def test_yaml_fences_do_not_open_the_shape(self):
        body = yaml.safe_dump(self.atom(), sort_keys=False)
        self.assertEqual("MOLECULE", mapping(f"```yaml\n{body}```")["result"])

    def test_a_gate_that_runs_an_owned_test_needs_the_flag(self):
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_app.py").write_text("present = True\n", "utf-8")
        owned = self.atom(files=["app.py", "tests/test_app.py"],
                          gate="set -e -o pipefail\npython3 -m unittest tests.test_app")
        with self.assertRaises(ValueError) as caught:
            self.check(owned)
        self.assertIn("gate_files_are_the_work", str(caught.exception))
        self.assertEqual("MOLECULE", self.check(
            self.atom(files=["app.py", "tests/test_app.py"],
                      gate="set -e -o pipefail\npython3 -m unittest tests.test_app",
                      gate_files_are_the_work=True))["result"])


class MissingAtomsTest(unittest.TestCase):
    def test_the_refusal_says_to_write_an_empty_atoms_list(self):
        # a refusal that does not name the fix costs a whole repair round (T5)
        body = {"result": "MOLECULE", "reason": "why", "molecule": {
            "name": "small", "source": ["specs/a.md:1"], "goal": "g", "why": "w",
            "needs": [], "files": ["app.py"], "gate": "set -e -o pipefail\nfalse", "done_when": "proof"}}
        with self.assertRaises(ValueError) as caught:
            validate(body, repo=pathlib.Path("."), sources=[], rows=[], target=None)
        self.assertIn("atoms: []", str(caught.exception))


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
