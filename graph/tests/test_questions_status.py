"""A spec the grill sent back with questions is marked `lean_status: questions`, so nothing mistakes it for a
spec that is merely waiting: the dashboard shows `? awaiting answer` and its attention filter lists it."""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lean
import lean_git
import lean_run
import lean_spec
import project_specs
import project_view
import tmp_root  # noqa: F401
from test_keep import repo
from test_lean import PROFILE_TEXT
from workspace import Workspace

EXPECTED_TESTS = 4


class Marked(unittest.TestCase):
    def setUp(self):
        self.repo = repo()
        (pathlib.Path(self.repo) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("Mechanics are in [profile-test.md](profile-test.md).\n")
        self.ws = Workspace(tempfile.mkdtemp())
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        self.spec.write_text("Restyle the Log screen.\n")
        patched = mock.patch.object(lean_git, "unmerged", return_value=[])
        patched.start()
        self.addCleanup(patched.stop)

    def argv(self):
        return ["--workspace", str(self.ws.root), "--repo", self.repo, "--spec", str(self.spec)]

    def test_a_grill_that_sends_questions_back_marks_the_spec(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        with mock.patch.object(lean_run, "grill", return_value="Which colour?"), \
                mock.patch.object(lean_run, "run_feature") as feature:
            self.assertEqual(2, lean.main(self.argv()))
        feature.assert_not_called()
        self.assertEqual("questions", lean_spec.front(self.spec.read_text())["lean_status"])

    def test_after_the_answers_the_spec_is_grilled_again(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.spec.write_text("---\nlean_status: questions\n---\nRestyle the Log screen.\n")
        with mock.patch.object(lean_run, "grill", return_value="") as grill, \
                mock.patch.object(lean_run, "run_feature", return_value="") as feature:
            lean.main(self.argv())
        grill.assert_called_once()
        feature.assert_called_once()


class Shown(unittest.TestCase):
    def project(self, statuses):
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "docs" / "lean").mkdir(parents=True)
        for name, status in statuses.items():
            head = f"---\nlean_status: {status}\n---\n" if status else ""
            (root / "docs" / "lean" / f"{name}.md").write_text(head + "Spec.\n")
        return str(root)

    def test_the_dashboard_marks_it_and_the_attention_filter_lists_it(self):
        root = self.project({"01-a": "questions", "02-b": "pr_open", "03-c": None, "04-d": "stopped"})
        text = project_view.report(root, [], 0, None)
        self.assertIn("? awaiting answer  01-a", text)
        self.assertIn("1 awaiting answer", text.splitlines()[0])
        attention = project_view.report(root, [], 0, "attention")
        self.assertEqual(["? awaiting answer  01-a", "● pr open          02-b", "✖ stopped          04-d"],
                         [line for line in attention.splitlines() if line and line[0] in "?●✖"])

    def test_built_and_building_still_come_first_and_the_mark_fits_the_column(self):
        self.assertEqual(project_view.WIDTH, max(len(mark) for mark in project_specs.MARKS))
        self.assertEqual(17, len(project_specs.QUESTION))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
