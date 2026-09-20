"""TRIAGE reads the join record and classifies the incidents that bought it."""

from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))

from triage_evidence import Ending
from triage_signatures import classify

EXPECTED_TESTS = 13
# A real gate output, kept for its bytes: a suite whose fixture never came up
# ran no test at all and still failed. One loopback address in it was changed
# to a host name, which no rule here reads.
REAL_GATE_OUTPUT = HERE / "tests/fixtures/gate-output-environment.txt"


def ending(*events, output=None, history=(), card=None, artifacts=None):
    artifacts = artifacts or ({} if output is None else {"gate-output": (output,)})
    return Ending("T1", card or {"id": "T1", "status": "todo",
                                 "files": ["simulation/app.py"]},
                  tuple(events), artifacts, tuple(history))


class SignatureTest(unittest.TestCase):
    def test_an_empty_boundary_has_no_cause(self):
        self.assertIsNone(classify(ending({"kind": "claimed"},
                                          {"kind": "released"})))

    def test_a_failing_gate_that_printed_nothing_is_the_gate(self):
        said = classify(ending({"kind": "failed", "step": "gate"}, output=""))
        self.assertEqual(("gate", "mute-gate"), (said.verdict, said.signature))

    def test_a_real_zero_test_failure_is_environment(self):
        output = REAL_GATE_OUTPUT.read_text("utf-8")
        said = classify(ending({"kind": "failed", "step": "gate"}, output=output))
        self.assertEqual("environment", said.verdict)
        for marker in ("ModuleNotFoundError", "never came up", "Ran 0 tests"):
            with self.subTest(marker=marker):
                said = classify(ending({"kind": "failed", "step": "gate"},
                                       output=f"{marker}: the retained shape"))
                self.assertEqual("environment", said.verdict)
        self.assertIn("Ran 0 tests", output)  # retained incident, not a toy

    def test_a_file_outside_the_card_is_the_rig(self):
        output = "File /tmp/drive-x/task-T1/simulation/tests/other.py, line 4"
        said = classify(ending({"kind": "failed", "step": "gate"}, output=output))
        self.assertEqual(("rig", "outside-file:simulation/tests/other.py"),
                         (said.verdict, said.signature))
        other_root = classify(ending({"kind": "failed", "step": "gate"},
                                     output="docs/rules.md failed"))
        self.assertEqual("rig", other_root.verdict)

    def test_a_speaking_gate_repeating_is_work(self):
        first = "AssertionError at /tmp/drive-a/task-T1/simulation/app.py:44"
        again = "AssertionError at /tmp/drive-b/task-T1/simulation/app.py:44"
        said = classify(ending({"kind": "failed", "step": "gate"},
                               output=again, history=(first, again)))
        self.assertEqual("work", said.verdict)
        self.assertTrue(said.signature.startswith("repeat-gate:"))

    def test_two_lines_of_one_file_are_two_failures(self):
        """The worktree root is what changes between rounds; the line the
        assertion failed on is the failure itself. Blanking anything that
        looked like a port read line 44 and line 55 as one repeat, and parked
        a card as a spin for two different failures."""
        first = "AssertionError at /tmp/drive-a/task-T1/simulation/app.py:44 in test_one"
        again = "AssertionError at /tmp/drive-b/task-T1/simulation/app.py:55 in test_one"
        said = classify(ending({"kind": "failed", "step": "gate"},
                               output=again, history=(first, again)))
        self.assertEqual(("unknown", "unmatched-gate"), (said.verdict, said.signature))

    def test_a_review_that_did_not_happen_is_harness(self):
        said = classify(ending({"kind": "review_unavailable",
                                "why": "the diff review did not happen"}))
        self.assertEqual("harness", said.verdict)
        accepted = classify(ending({"kind": "failed", "step": "gate"},
                                   {"kind": "accepted"}, output="Ran 0 tests",
                                   card={"id": "T1", "status": "done",
                                         "files": ["simulation/app.py"]}))
        self.assertIsNone(accepted)
        historical = classify(ending(
            {"kind": "failed", "step": "gate"}, output="Ran 0 tests",
            card={"id": "T1", "status": "done", "files": ["simulation/app.py"]}))
        self.assertEqual("environment", historical.verdict)

    def test_the_naming_law_is_contract(self):
        said = classify(ending({"kind": "refused", "step": "names",
                                "why": "this card uses names that are not there"}))
        self.assertEqual("contract", said.verdict)

    def test_red_first_is_contract_unless_the_gate_never_ran(self):
        refused = {"kind": "refused", "step": "red_first"}
        said = classify(ending(refused, artifacts={"red-first": (
            "the gate already passes, so it proves nothing",)}))
        self.assertEqual("contract", said.verdict)
        missing = classify(ending(refused, artifacts={"red-first": (
            "bash: tools/gate.sh: No such file or directory",)}))
        self.assertEqual("environment", missing.verdict)
        wrapper = classify(ending(refused, artifacts={"red-first": (
            "the gate could not run (crash): [Errno 2]",)}))
        self.assertEqual("environment", wrapper.verdict)

    def test_a_person_queue_stays_unknown_without_losing_its_reason(self):
        said = classify(ending({"kind": "needs_a_person", "why": "inspect the stack"}))
        self.assertEqual(("unknown", "person-queued", "inspect the stack"),
                         (said.verdict, said.signature, said.why))

    def test_quarantine_uses_mechanical_causes_before_work(self):
        generic = classify(ending({"kind": "quarantined",
                                   "why": "9 turns finished and nothing was accepted"}))
        wrong = classify(ending({"kind": "quarantined",
                                 "why": "T7 ended at gate the same way 2 times: red"}))
        mute = classify(ending({"kind": "quarantined",
                                "why": "T1 ended at gate the same way 2 times:  — the next turn"}))
        broken = classify(ending({"kind": "quarantined", "why":
                                  "T1 ended at gate the same way 2 times: "
                                  "line 242 in start_fakes — the next turn"},
                                 history=("ModuleNotFoundError: no module x",)))
        own = classify(ending({"kind": "quarantined", "why":
                               "T1 ended at gate the same way 2 times: "
                               "new.py: No such file or directory — the next turn"},
                              card={"id": "T1", "status": "quarantined",
                                    "files": ["new.py"]}))
        self.assertEqual(("harness", "harness", "gate", "environment", "work"),
                         (generic.verdict, wrong.verdict, mute.verdict,
                          broken.verdict, own.verdict))

    def test_an_unmatched_first_failure_stays_unknown(self):
        said = classify(ending({"kind": "failed", "step": "gate"},
                               output="one clear assertion failed"))
        self.assertEqual("unknown", said.verdict)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
