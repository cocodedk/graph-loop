"""A builder call has a spend cap, and hitting it stops the feature with a clear reason.

The CLI reports a cap as subtype `error_max_budget_usd`, is_error true and no `result`; it checks the cap
per turn, so one long turn can pass it. The lean loop's own rules then do the rest: no repair, the
worktree kept, the spec marked stopped, the reason mailed (`test_lean_run.Rig`)."""

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lean_run
import providers
import tmp_root  # noqa: F401
from providers import Outcome, claude
from test_lean_run import Rig
from test_providers import fake

EXPECTED_TESTS = 4
OVER = {"is_error": True, "subtype": "error_max_budget_usd", "total_cost_usd": 41.7, "session_id": "s9",
        "errors": ["Reached maximum budget ($40)"], "usage": {"input_tokens": 9, "output_tokens": 9},
        "permission_denials": []}


class Cap(unittest.TestCase):
    def answer(self, body, **kw):
        binary = fake("cat > /dev/null; echo \"$@\" > $OUT; echo '" + json.dumps(body) + "'")
        with tempfile.NamedTemporaryFile("r", delete=False) as handle:
            os.environ["OUT"] = handle.name
            out = claude(binary, "prompt", account="work", **kw)
            return out, pathlib.Path(handle.name).read_text()

    def test_the_cap_is_passed_to_the_cli_only_when_given(self):
        self.assertIn("--max-budget-usd 40", self.answer({"result": "ok", **OVER, "is_error": False,
                                                          "subtype": "success"}, budget=40)[1])
        self.assertNotIn("--max-budget-usd", self.answer({"result": "ok", "usage": OVER["usage"],
                                                          "permission_denials": []})[1])

    def test_a_cap_answer_is_its_own_kind_and_says_what_to_do(self):
        out, _ = self.answer(OVER, budget=40)
        self.assertEqual(("budget", 41.7, "s9"), (out.kind, out.cost, out.session))
        for words in ("$40", "$41.70", "work so far is kept", "Split the spec", "BUILD_BUDGET"):
            self.assertIn(words, out.text)
        self.assertFalse(out.ok)


class Stop(Rig):
    def test_a_cap_stop_sends_no_repair_keeps_the_work_and_mails_the_reason(self):
        def spent(ws, task, prompt, tree, resume="", effort=""):
            self.prompts.append(prompt)
            (pathlib.Path(tree.path) / "ring.py").write_text("half done\n")
            return Outcome("budget", text="the builder reached its spend cap of $40")
        self.assertEqual("", self.run_it(spent, suites=(), reviews=()))
        self.assertEqual(1, len(self.prompts))                         # a repair would spend it again
        stopped = next(row for row in self.ws.events() if row["kind"] == "lean_stopped")
        self.assertTrue((pathlib.Path(stopped["tree"]) / "ring.py").is_file())   # the work is kept
        self.assertIn("lean_status: stopped", self.spec.read_text())
        self.assertIn("spend cap of $40", self.mails[0][1])

    def test_the_lean_builder_is_given_the_cap(self):
        with mock.patch.object(providers, "claude", return_value=Outcome("ok")) as call:
            lean_run.build(self.ws, {"id": "x", "gate": "true"}, "build it", mock.Mock(path="/tmp"))
        self.assertEqual(lean_run.BUILD_BUDGET, call.call_args.kwargs["budget"])
        self.assertEqual(40, lean_run.BUILD_BUDGET)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
