"""Every graph skill tells an agent where to file a fault in graph-loop and how to grade it."""

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2] / "plugins" / "graph"


class Skills(unittest.TestCase):
    def test_each_skill_names_the_issues_page_the_command_and_all_four_grades(self):
        skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(["dashboard", "graph", "run"], [path.parent.name for path in skills])
        for path in skills:
            text = path.read_text("utf-8")
            with self.subTest(skill=path.parent.name):
                self.assertIn("https://github.com/cocodedk/graph-loop/issues", text)
                self.assertIn("gh issue create --repo cocodedk/graph-loop", text)
                for grade in ("P0", "P1", "P2", "P3"):
                    self.assertIn(f"`{grade}`", text)

    def test_the_plugin_version_moved_with_the_skills(self):
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))["version"]
        self.assertEqual("0.4.2", version)


if __name__ == "__main__":
    unittest.main()
