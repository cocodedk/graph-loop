"""A reviewer may not write to what it grades.

`--allowedTools` is additive: naming Read, Grep and Glob leaves the session's
Bash, Edit and Write in place. The deny list existed and nothing passed it.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import providers
import review
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import tools
from test_providers import fake, result

EXPECTED_TESTS = 4


class TheFallbackReviewerCannotWrite(unittest.TestCase):
    def call(self) -> dict:
        seen = {}

        def fake(binary, prompt, **kwargs):
            seen.update(kwargs)
            return providers.Outcome("ok", text="REVIEW: ACCEPT")

        with unittest.mock.patch.object(providers, "claude", fake):
            review._claude_review("read this", review.resources.Resource(
                "claude", None, "claude-opus-5"), "high", 60)
        return seen

    def test_everything_that_writes_or_runs_is_denied_by_name(self):
        denied = self.call()["disallowed_tools"]
        for tool in ("Bash", "Edit", "Write", "NotebookEdit"):
            self.assertIn(tool, denied)

    def test_the_deny_list_is_the_one_tools_declares(self):
        self.assertEqual(self.call()["disallowed_tools"], tools.READ_ONLY_DENIES)

    def test_it_may_still_read(self):
        self.assertEqual(self.call()["allowed_tools"], tools.READ)


class TheFallbackReviewerHasOnlyReadingTools(unittest.TestCase):
    """Denying by name leaves whatever the session already had, an inherited
    MCP server included. `--tools` is what bounds it, and
    `--strict-mcp-config` is what keeps that server out — the two flags the
    slicer's planner already calls claude with."""

    def test_the_call_carries_the_read_only_flags(self):
        answer = result(result="REVIEW: ACCEPT")
        with tempfile.TemporaryDirectory() as folder:
            written = pathlib.Path(folder) / "argv"
            binary = fake(f"cat > /dev/null; echo \"$@\" > {written}; echo '{answer}'")
            with unittest.mock.patch.dict(os.environ, {"DRIVE_CLAUDE": binary}):
                out = review._claude_review("read this", review.resources.Resource(
                    "claude", "work", "claude-opus-5"), "high", 60)
            argv = written.read_text()
        self.assertEqual("ACCEPT", out.verdict)
        self.assertIn(f"--tools {tools.READ} --strict-mcp-config", argv)


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
