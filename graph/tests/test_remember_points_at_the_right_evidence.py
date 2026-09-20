"""A section points at the artifact of ITS OWN run, and says only what the log
says.

Three faults an independent review found. Matching by distance in the log
picked another run's file as soon as a second lane logged in between — the
campaign writes one stream and three cards write into it at once, so distance
in that stream means nothing. An artifact row whose `task` or `name` is not a
string went into a dictionary key and took the whole export down with a
TypeError. And every `rejected` event was called a diff review's doing, though
the loop writes that same event for an exhausted harness retry and for a gate
that never passed, with nothing in it to tell them apart.
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

EXPECTED_TESTS = 7


def vault() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    piece = root / "T30"
    piece.mkdir(parents=True)
    (piece / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (piece / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    (piece / "01-producer.md").write_text(
        cardfile.dump({"goal": "the record carries it", "status": "todo"}), "utf-8")
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


def two_lanes() -> list[dict]:
    """T30.schema's second gate run, with T30.producer's lane logging between
    the run and the output it wrote. The previous run's output is one event
    away from the second run's step; its own is five."""
    return [
        {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
         "added": ["T30", "T30.schema", "T30.producer"]},
        gate("2026-09-20T07:05:00Z", "T30.schema", 1),
        artifact("gate-output", 1, "T30.schema", "2026-09-20T07:05:01Z"),
        gate("2026-09-20T07:20:00Z", "T30.schema", 0),
        {"at": "2026-09-20T07:20:01Z", "kind": "attempt", "task": "T30.producer",
         "account": "work", "outcome": "ok", "counted": True},
        {"at": "2026-09-20T07:20:02Z", "kind": "attempt", "task": "T30.producer",
         "account": "work", "outcome": "ok", "counted": True},
        gate("2026-09-20T07:20:03Z", "T30.producer", 0),
        artifact("gate-output", 1, "T30.producer", "2026-09-20T07:20:04Z"),
        artifact("gate-output", 2, "T30.schema", "2026-09-20T07:20:05Z"),
    ]


def step(at: str, task: str, name: str) -> dict:
    return {"at": at, "kind": "step", "task": task, "step": name, "seconds": 3.0}


def reviews() -> list[dict]:
    """A contract review that PASSED, then one that refused. The passing
    round writes an answer and no refusal, so bounding a refusal by the
    refusals around it puts the passing round's answer inside its reach."""
    return [
        {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
         "added": ["T30", "T30.schema"]},
        step("2026-09-20T07:00:00Z", "T30.schema", "contract"),
        artifact("contract-answer", 1, "T30.schema", "2026-09-20T07:00:01Z"),
        step("2026-09-20T07:10:00Z", "T30.schema", "contract"),
        {"at": "2026-09-20T07:10:02Z", "kind": "refused", "task": "T30.schema",
         "step": "contract", "why": "the gate can pass without the work"},
    ]


def rounds() -> list[dict]:
    """A contract review that passed, a second that refused, and the third
    round's answer written straight after the refusal — nearer to it than the
    answer that caused it."""
    return [
        {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
         "added": ["T30", "T30.schema"]},
        step("2026-09-20T06:59:00Z", "T30.schema", "contract"),
        artifact("contract-answer", 1, "T30.schema", "2026-09-20T07:00:00Z"),
        {"at": "2026-09-20T07:01:00Z", "kind": "attempt", "task": "T30.producer",
         "account": "work", "outcome": "ok", "counted": True},
        {"at": "2026-09-20T07:02:00Z", "kind": "attempt", "task": "T30.producer",
         "account": "work", "outcome": "ok", "counted": True},
        gate("2026-09-20T07:03:00Z", "T30.producer", 0),
        {"at": "2026-09-20T07:04:00Z", "kind": "refused", "task": "T30.schema",
         "step": "contract", "why": "the gate can pass without the work"},
        step("2026-09-20T07:04:30Z", "T30.schema", "contract"),
        artifact("contract-answer", 2, "T30.schema", "2026-09-20T07:05:00Z"),
    ]


def written(root: pathlib.Path) -> str:
    return (root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8")


class EvidenceBelongsToTheRunThatMadeIt(unittest.TestCase):
    def test_a_gate_names_the_output_its_own_run_wrote_not_the_nearest(self):
        root = vault()
        remember.write_memory(root, two_lanes())
        green = written(root).split("the gate ran, exit 0")[1]
        self.assertIn("002-gate-output.txt", green)
        self.assertNotIn("001-gate-output.txt", green)

    def test_a_refusal_names_the_answer_before_it_not_the_next_rounds(self):
        root = vault()
        remember.write_memory(root, rounds())
        refusal = written(root).split("refused at contract")[1]
        self.assertIn("001-contract-answer.txt", refusal)
        self.assertNotIn("002-contract-answer.txt", refusal)

    def test_a_run_whose_output_never_landed_names_no_file_at_all(self):
        """A campaign that died between the two: no pointer beats a wrong one."""
        root = vault()
        remember.write_memory(root, [gate("2026-09-20T07:05:00Z", "T30.schema", 0)])
        self.assertNotIn("calls/", written(root))


class AnInterruptedRunBorrowsNobodysEvidence(unittest.TestCase):
    """A campaign killed between a gate and the artifact it was about to write
    leaves a run with no output. The next run of the same card writes one —
    and it is not this run's, however near it sits."""

    def setUp(self):
        self.root = vault()
        remember.write_memory(self.root, [
            {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
             "added": ["T30", "T30.schema"]},
            gate("2026-09-20T07:05:00Z", "T30.schema", 1),       # killed before its write
            gate("2026-09-20T07:20:00Z", "T30.schema", 0),
            artifact("gate-output", 1, "T30.schema", "2026-09-20T07:20:01Z"),
        ])
        self.red, self.green = written(self.root).split("the gate ran, exit ")[1:]

    def test_the_interrupted_run_points_at_no_file_at_all(self):
        self.assertNotIn("calls/", self.red)

    def test_it_says_the_evidence_never_reached_the_log(self):
        self.assertIn("did not reach the log", self.red)

    def test_the_run_that_did_write_one_still_names_it(self):
        self.assertIn("001-gate-output.txt", self.green)


class ARefusalNeverBorrowsAPassingReviewsAnswer(unittest.TestCase):
    def test_its_own_execution_wrote_no_answer_so_it_names_none(self):
        root = vault()
        remember.write_memory(root, reviews())
        refusal = written(root).split("refused at contract")[1]
        self.assertNotIn("001-contract-answer.txt", refusal)
        self.assertIn("did not reach the log", refusal)


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
