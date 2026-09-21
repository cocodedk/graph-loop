"""A section says what the log says, and a row it cannot use costs only itself.

`rejected` is the case that set the rule. The loop writes that same event when
a diff review finds something, when a harness retry runs out and when a gate
never passes (`loop_judge_retry.py`, `worktree_refs.py`), and nothing in the
event tells those apart — so the section says the card was rejected, points at
the log by its time, and names no reviewer and no file.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import remember
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 4


def vault() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    piece = root / "T30"
    piece.mkdir(parents=True)
    (piece / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (piece / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    return root


def call(name: str, number: int, task: str) -> str:
    return str(pathlib.Path(tempfile.gettempdir()) / "campaign" / "calls" / task /
               f"{number:03d}-{name}.txt")


def artifact(name: str, number: int, task: str, at: str) -> dict:
    return {"at": at, "kind": "artifact", "task": task, "name": name,
            "path": call(name, number, task), "bytes": 40}


def gate(at: str, task: str, code: int) -> dict:
    return {"at": at, "kind": "step", "task": task, "step": "gate",
            "seconds": 5.0, "passed": not code, "code": code}


def written(root: pathlib.Path) -> str:
    return (root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8")


class ARowThatCannotBeUsedIsCountedNotRaised(unittest.TestCase):
    def test_an_artifact_whose_task_or_name_is_not_a_string_stops_nothing(self):
        root = vault()
        counts = remember.write_memory(root, [
            {"at": "2026-09-20T07:00:00Z", "kind": "artifact", "task": ["T30.schema"],
             "name": "gate-output", "path": call("gate-output", 1, "T30.schema")},
            {"at": "2026-09-20T07:00:01Z", "kind": "artifact", "task": "T30.schema",
             "name": {"gate": "output"}, "path": call("gate-output", 1, "T30.schema")},
            gate("2026-09-20T07:05:00Z", "T30.schema", 0),
        ])
        self.assertEqual(2, counts["no_section"])
        self.assertIn("the gate ran, exit 0", written(root))


class ARejectionIsOnlyWhatTheLogSays(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        remember.write_memory(self.root, [
            {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
             "added": ["T30", "T30.schema"]},
            artifact("diff-review-answer", 1, "T30.schema", "2026-09-20T07:00:00Z"),
            {"at": "2026-09-20T07:40:00Z", "kind": "rejected", "task": "T30.schema",
             "why": "3 rounds running; a person re-slices"},
        ])
        self.section = written(self.root).split("2026-09-20 — ")[-1]

    def test_it_never_names_a_reviewer_or_a_review(self):
        """The loop writes this event for an exhausted harness retry and for a
        gate that stayed red, with nothing in it to tell those apart."""
        self.assertNotIn("review", self.section.lower())

    def test_it_points_at_the_log_rather_than_at_a_reviewers_file(self):
        self.assertNotIn("calls/", self.section)
        self.assertIn("2026-09-20T07:40:00Z", self.section)


class ARefusalNamesWhoActuallyMadeIt(unittest.TestCase):
    def test_a_scope_refusal_is_the_loops_own_check_not_a_reviewer(self):
        """`Loop.run_task` refuses a card whose gate reaches outside its files
        before any reviewer is called. Calling that a review is provenance the
        log does not carry."""
        root = vault()
        remember.write_memory(root, [
            {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
             "added": ["T30", "T30.schema"]},
            {"at": "2026-09-20T07:01:06Z", "kind": "refused", "task": "T30.schema",
             "step": "scope_of_gate", "why": "the gate reaches outside this card"}])
        section = written(root).split("refused at scope_of_gate")[1]
        self.assertNotIn("review", section.lower())
        self.assertIn("loop", section.lower())


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
