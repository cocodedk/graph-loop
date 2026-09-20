"""Combined failures are compared in full with their candidate's exact parent."""

from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — isolate all checkouts
from gates import GateResult
from keep import CombinedGateFailed, Keeper
from keep_failure import GateFailure
from loop_judge_gates import _gate_is_defective
from test_keep import repo
from test_keep_combined_owner import BROKEN, keeper_loop
from test_loop import Fakes, task
from worktree import Worktree

# The extra failure is BEFORE an identical tail longer than the display limit.
TAIL = 'printf "%0500d\\n" 0'
GATE = f'if grep -q two a.py; then echo new-Y; fi; echo old-X; {TAIL}; exit 1'


class BaselineTest(unittest.TestCase):
    def test_an_old_failure_does_not_hide_an_extra_failure_before_the_same_tail(self):
        loop, book, _ = keeper_loop(task(), Fakes(), [{**BROKEN, "gate": GATE}])
        loop.run_task(book.task("T1"))
        self.assertEqual("done", book.task("T9")["status"])
        self.assertEqual(1, book.task("T1")["rebuild_round"])
        self.assertNotIn("T9", book.task("T1")["needs"])

    def test_the_same_failure_is_still_routed_to_its_owner(self):
        loop, book, _ = keeper_loop(task(), Fakes(), [BROKEN])
        loop.run_task(book.task("T1"))
        self.assertEqual("todo", book.task("T9")["status"])
        self.assertIn("T9", book.task("T1")["needs"])
        self.assertEqual(0, int(book.task("T1").get("rebuild_round") or 0))

    def test_the_exception_keeps_the_full_result_and_exact_commits(self):
        root = repo()
        keeper = Keeper(root, "campaign/test")
        base = keeper.tip()
        tree = Worktree(root, "NOW", base).create()
        pathlib.Path(tree.path, "a.py").write_text("two\n")
        with self.assertRaises(CombinedGateFailed) as caught:
            keeper.keep("NOW", tree.path, "change", files=["a.py"], gates=[GATE])
        fault = caught.exception
        self.assertEqual(base, fault.base)
        self.assertNotEqual(base, fault.failure.commit)
        self.assertEqual(1, fault.failure.result.code)
        self.assertEqual("ran", fault.failure.result.kind)
        self.assertTrue(fault.failure.result.output.startswith("new-Y\nold-X\n"))
        self.assertGreater(len(fault.failure.result.output), 400)

    def test_the_probe_uses_the_captured_parent_even_after_the_tip_moves(self):
        seen = []
        keeper = SimpleNamespace(tip=lambda: "moved-tip", _combined_tree_red=lambda _id, commit, _gates:
                                 seen.append(commit))
        loop = SimpleNamespace(keeper=keeper, space=SimpleNamespace(event=lambda *a, **k: None,
                                                                    artifact=lambda *a, **k: None))
        failure = GateFailure("false", GateResult(1, "X"), "candidate", "/candidate")
        clash = SimpleNamespace(gate="false", base="captured-parent", failure=failure)
        self.assertFalse(_gate_is_defective(loop, {"id": "T1"}, clash))
        self.assertEqual(["captured-parent"], seen)

    def test_baseline_timeout_is_unknown_instead_of_proof_of_an_old_failure(self):
        failure = GateFailure("false", GateResult(1, "X"), "candidate", "/candidate")
        baseline = GateFailure("false", GateResult(124, "X", kind="timeout"), "parent", "/base")
        keeper = SimpleNamespace(tip=lambda: "parent", _combined_tree_red=lambda *args: baseline)
        loop = SimpleNamespace(keeper=keeper, space=SimpleNamespace(event=lambda *a, **k: None,
                                                                    artifact=lambda *a, **k: None))
        self.assertIsNone(_gate_is_defective(loop, {"id": "T1"},
                                            SimpleNamespace(gate="false", base="parent", failure=failure)))

    def test_only_the_known_checkout_path_is_normalized(self):
        failure = GateFailure("false", GateResult(1, "/candidate/a.py: X"), "candidate", "/candidate")
        baseline = GateFailure("false", GateResult(1, "/base/a.py: X"), "parent", "/base")
        loop = SimpleNamespace(
            keeper=SimpleNamespace(_combined_tree_red=lambda *args: baseline),
            space=SimpleNamespace(event=lambda *a, **k: None, artifact=lambda *a, **k: None))
        clash = SimpleNamespace(gate="false", base="parent", failure=failure)
        self.assertTrue(_gate_is_defective(loop, {"id": "T1"}, clash))
        baseline.result.output = "/base/a.py: Y"
        self.assertFalse(_gate_is_defective(loop, {"id": "T1"}, clash))

    def test_the_same_output_with_a_different_exit_is_not_the_same_failure(self):
        failure = GateFailure("false", GateResult(1, "X"), "candidate", "/candidate")
        baseline = GateFailure("false", GateResult(2, "X"), "parent", "/base")
        loop = SimpleNamespace(
            keeper=SimpleNamespace(_combined_tree_red=lambda *args: baseline),
            space=SimpleNamespace(event=lambda *a, **k: None, artifact=lambda *a, **k: None))
        self.assertFalse(_gate_is_defective(loop, {"id": "T1"},
                                           SimpleNamespace(gate="false", base="parent", failure=failure)))

    def test_a_slower_rerun_of_the_same_failure_is_still_the_same_failure(self):
        ran = "AssertionError: missing ABSTAIN\nRan 1 test in 0.674s\nFAILED (failures=1)\n"
        slower = ran.replace("0.674s", "0.676s")
        saved = []
        failure = GateFailure("g", GateResult(1, ran), "candidate", "/candidate")
        baseline = GateFailure("g", GateResult(1, slower), "parent", "/base")
        loop = SimpleNamespace(
            keeper=SimpleNamespace(_combined_tree_red=lambda *args: baseline),
            space=SimpleNamespace(event=lambda *a, **k: None,
                                  artifact=lambda _id, _name, text: saved.append(text)))
        clash = SimpleNamespace(gate="g", base="parent", failure=failure)
        self.assertTrue(_gate_is_defective(loop, {"id": "T1"}, clash))
        self.assertIn("0.674s", saved[0])                        # the kept evidence is untouched
        self.assertIn("0.676s", saved[0])
        for changed in (slower.replace("Ran 1 test", "Ran 2 tests"),
                        slower.replace("ABSTAIN", "INVESTIGATE"), slower + "another failure\n"):
            baseline.result.output = changed
            self.assertFalse(_gate_is_defective(loop, {"id": "T1"}, clash), changed)

    def test_the_suite_asserts_its_own_size(self):
        self.assertEqual(9, unittest.TestLoader().loadTestsFromTestCase(type(self)).countTestCases())
