"""The dashboard shows what each spec cost the builder. Claude reports a resumed call's cost as its
session's running total, so a session counts once (its largest value) and a spec's sessions add up."""

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import project_cost
import project_view
import tmp_root  # noqa: F401
from test_project_marks import git, project, using

EXPECTED_TESTS = 5


def started(task, at="t1"):
    return {"kind": "lean_feature_started", "task": task, "at": at}


def build(task, cost, purpose="build"):
    return {"kind": "attempt", "task": task, "purpose": purpose, "cost": cost}


def write(root, name, rows, raw=""):
    folder = pathlib.Path(root) / "scratchpad" / "lean"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("".join(json.dumps(row) + "\n" for row in rows) + raw)


class Costs(unittest.TestCase):
    def test_repairs_in_one_session_count_once_and_two_runs_add(self):
        root = project()
        write(root, "events.jsonl", [
            started("01-a"), build("01-a", 1.0), build("01-a", 1.5), build("01-a", 2.0),
            started("01-a", "t2"), build("01-a", 0.5),                  # a later run: a new session
            started("02-b"), build("02-b", 0.25), build("02-b", 3.0, "review")])   # only the builder's calls
        self.assertEqual({"01-a": 2.5, "02-b": 0.25}, project_cost.card_costs(str(root)))

    def test_rotated_files_are_read_and_bad_lines_and_costs_are_skipped(self):
        root = project()
        write(root, "events-0001.jsonl", [started("01-a"), build("01-a", 1.0)])
        write(root, "events.jsonl", [started("02-b"), build("02-b", None), build("02-b", "x"), build("02-b", True),
                                     build("02-b", 0.75)], raw="{broken\n")
        self.assertEqual({"01-a": 1.0, "02-b": 0.75}, project_cost.card_costs(str(root)))

    def test_no_workspace_means_no_costs(self):
        self.assertEqual({}, project_cost.card_costs(str(project())))


class Shown(unittest.TestCase):
    def report(self, root):
        with using(git(["feat(01-a): x"])):
            return project_view.report(str(root), [], 0, None)

    def test_the_view_has_a_cost_column_only_when_there_is_cost_data(self):
        root = project(**{"01-a.md": "", "02-b.md": ""})
        self.assertNotIn("$", self.report(root))
        write(root, "events.jsonl", [started("01-a"), build("01-a", 1.5)])
        lines = self.report(root).splitlines()
        self.assertIn("✔ built     01-a  $1.50", lines)
        self.assertIn("· waiting   02-b", lines)                      # no cost yet: no figure

    def test_costs_line_up_right_aligned(self):
        root = project(**{"01-a.md": "", "02-longer-name.md": ""})
        write(root, "events.jsonl", [started("01-a"), build("01-a", 0.5), started("02-longer-name"),
                                     build("02-longer-name", 12.0)])
        rows = [line for line in self.report(root).splitlines() if "$" in line]
        self.assertEqual(1, len({len(line) for line in rows}))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
