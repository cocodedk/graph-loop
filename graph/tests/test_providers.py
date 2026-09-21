"""What a provider call returns, and what the loop is allowed to conclude from it.

Written before `providers.py`. Every case runs a fake executable, so nothing here
spends an account or touches a model.
"""

from __future__ import annotations

import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import claude, codex

EXPECTED_TESTS = 13


def fake(script: str) -> str:
    """A throwaway executable that prints what a real one would."""
    folder = tempfile.mkdtemp()
    path = pathlib.Path(folder) / "fake"
    path.write_text("#!/bin/bash\n" + script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def result(**fields) -> str:
    body = {"result": "done", "total_cost_usd": 0.5,
            "usage": {"input_tokens": 10, "output_tokens": 20},
            "permission_denials": []}
    body.update(fields)
    return json.dumps(body)


class ClaudeTest(unittest.TestCase):
    def test_a_finished_call_is_ok_and_carries_its_cost(self):
        binary = fake(f"cat > /dev/null; echo '{result()}'")
        out = claude(binary, "prompt", account="work")
        self.assertEqual((True, "ok"), (out.ok, out.kind))
        self.assertEqual(0.5, out.cost)
        self.assertEqual("done", out.text)

    def test_a_usage_limit_is_not_a_failure_and_consumes_no_attempt(self):
        binary = fake("cat > /dev/null; echo \"You've hit your weekly limit · resets 11pm\"")
        out = claude(binary, "prompt", account="work")
        self.assertEqual("limit", out.kind)
        self.assertFalse(out.ok)
        self.assertFalse(out.consumes_attempt)

    def test_a_denial_before_any_work_is_a_harness_fault(self):
        denials = result(permission_denials=[{"tool": "Edit"}], result="")
        binary = fake(f"cat > /dev/null; echo '{denials}'")
        out = claude(binary, "prompt", account="work")
        self.assertEqual("harness", out.kind)
        self.assertFalse(out.consumes_attempt)

    def test_a_denial_the_builder_worked_around_does_not_lose_its_work(self):
        denials = result(permission_denials=[{"tool": "Bash"}], result="done anyway")
        binary = fake(f"cat > /dev/null; echo '{denials}'")
        out = claude(binary, "prompt", account="work")
        self.assertEqual("ok", out.kind)
        self.assertEqual(1, out.denials)
        self.assertEqual("done anyway", out.text)

    def test_an_authentication_failure_stops_the_provider(self):
        binary = fake("cat > /dev/null; echo 'Invalid API key · please run /login' >&2; exit 1")
        out = claude(binary, "prompt", account="work")
        self.assertEqual("auth", out.kind)
        self.assertFalse(out.consumes_attempt)

    def test_output_that_is_not_json_is_a_provider_fault(self):
        binary = fake("cat > /dev/null; echo 'half a sentence'")
        out = claude(binary, "prompt", account="work")
        self.assertEqual("malformed", out.kind)
        self.assertFalse(out.consumes_attempt)

    def test_a_model_that_worked_and_failed_its_own_gate_consumes_the_attempt(self):
        body = result(result="I could not do it")
        binary = fake(f"cat > /dev/null; echo '{body}'")
        out = claude(binary, "prompt", account="work")
        self.assertTrue(out.ok)
        self.assertTrue(out.consumes_attempt)

    def test_the_account_decides_the_configuration_directory(self):
        binary = fake("cat > /dev/null; echo \"[${CLAUDE_CONFIG_DIR-unset}]\" > $OUT; echo '"
                      + result() + "'")
        with tempfile.NamedTemporaryFile("r", delete=False) as handle:
            os.environ["OUT"] = handle.name
            claude(binary, "prompt", account="second")
            personal = pathlib.Path(handle.name).read_text().strip()
            claude(binary, "prompt", account="work")
            work = pathlib.Path(handle.name).read_text().strip()
        self.assertTrue(personal.endswith("/cfg/second]"), personal)
        # The work account is the default configuration: the variable must be
        # absent, not empty — an empty one points at a config with no login.
        self.assertEqual("[unset]", work)

    def test_a_planner_call_has_no_tools_at_all(self):
        binary = fake("cat > /dev/null; echo \"$@\" > $OUT; echo '" + result() + "'")
        with tempfile.NamedTemporaryFile("r", delete=False) as handle:
            os.environ["OUT"] = handle.name
            claude(binary, "prompt", account="work", no_tools=True)
            argv = pathlib.Path(handle.name).read_text()
        self.assertIn("--tools", argv)
        self.assertIn("--strict-mcp-config", argv)     # an inherited MCP server is not loaded
        self.assertNotIn("--allowedTools", argv)
        for family in ("Bash", "Edit", "Write", "Monitor", "WebFetch"):   # an inherited MCP tool too
            self.assertIn(family, argv.split("--disallowedTools")[1])

    def test_the_effort_is_medium_and_the_model_is_opus(self):
        binary = fake("cat > /dev/null; echo \"$@\" > $OUT; echo '" + result() + "'")
        with tempfile.NamedTemporaryFile("r", delete=False) as handle:
            os.environ["OUT"] = handle.name
            claude(binary, "prompt", account="work")
            argv = pathlib.Path(handle.name).read_text()
        self.assertIn("--model claude-opus-5", argv)
        self.assertIn("--effort medium", argv)
        self.assertNotIn("xhigh", argv)
        self.assertNotIn("max", argv)



class BannerTest(unittest.TestCase):
    def test_a_real_answer_beside_a_limit_banner_is_still_an_answer(self):
        # codex prints its usage banner on stderr — "your limit resets at ..." —
        # and reading that as a refusal threw away a finished review.
        binary = fake("echo 'REVIEW: ACCEPT'; echo 'tokens used 8,316; limit resets 18:00' >&2")
        out = codex(binary, "review this")
        self.assertEqual(("ok", "ACCEPT"), (out.kind, out.verdict))

    def test_a_claude_error_result_is_not_read_as_success(self):
        binary = fake("cat > /dev/null; echo '"
                      + result(is_error=True, result="Not logged in") + "'")
        out = claude(binary, "prompt", account="work")
        self.assertEqual("auth", out.kind)
        self.assertFalse(out.consumes_attempt)





class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
