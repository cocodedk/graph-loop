"""An unattended builder uses a supported, bounded Claude permission mode."""

import json
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import providers

EXPECTED_TESTS = 2


class ProviderModeTest(unittest.TestCase):
    def test_the_cli_accepts_the_mode_and_the_tool_fence_stays(self):
        response = subprocess.CompletedProcess([], 0, json.dumps({"result": "DONE"}), "")
        with patch.object(providers, "_run", return_value=response) as call:
            providers.claude("claude", "work", account="work", effort="medium",
                             allowed_tools="Read,Edit", disallowed_tools="Bash(git push *)")
        argv = call.call_args.args[0]
        self.assertEqual("dontAsk", argv[argv.index("--permission-mode") + 1])
        self.assertEqual("Read,Edit", argv[argv.index("--allowedTools") + 1])
        self.assertIn("Bash(git push *)", argv[argv.index("--disallowedTools") + 1])
        self.assertEqual("medium", argv[argv.index("--effort") + 1])

    def test_count(self):
        self.assertEqual(EXPECTED_TESTS, unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]).countTestCases())
