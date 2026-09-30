"""The `graph:dashboard` skill's shape: front matter, size, the commands it gives and what it never does."""

import json
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "graph"
SKILL = (PLUGIN / "skills" / "dashboard" / "SKILL.md").read_text("utf-8")
EXPECTED_TESTS = 5


class DashboardSkill(unittest.TestCase):
    def test_its_front_matter_names_it_and_says_when_to_use_it(self):
        front = yaml.safe_load(re.match(r"---\n(.*?)\n---\n", SKILL, re.DOTALL).group(1))
        self.assertEqual("dashboard", front["name"])
        self.assertTrue(front["description"].startswith("Use when"))

    def test_it_is_short_and_gives_the_commands_to_show_and_to_keep_it_open(self):
        self.assertLess(len(SKILL.splitlines()), 80)
        for text in ("loops.sh -1", "loops.py", "--only", "git rev-parse --show-toplevel", "type `!`"):
            self.assertIn(text, SKILL)

    def test_it_never_starts_stops_or_edits_anything(self):
        for word in (r"\bkill\b", r"\brm ", r"git push"):
            self.assertIsNone(re.search(word, SKILL), word)

    def test_the_plugin_is_at_the_version_that_carries_it_and_the_run_skill_points_to_it(self):
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text("utf-8"))
        self.assertGreaterEqual(tuple(map(int, manifest["version"].split("."))), (0, 4, 0))
        self.assertIn("graph:dashboard", (PLUGIN / "skills" / "run" / "SKILL.md").read_text("utf-8"))


class AccountsDoc(unittest.TestCase):
    def test_the_run_skill_says_where_accounts_are_set(self):
        run = (PLUGIN / "skills" / "run" / "SKILL.md").read_text("utf-8")
        for text in ("GRAPH_ACCOUNTS", "name=<CLAUDE_CONFIG_DIR>", "export GRAPH_ACCOUNTS=personal=<its config directory>"):
            self.assertIn(text, run)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
