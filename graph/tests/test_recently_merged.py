"""The project view lists what was merged to main that is not a spec, so hand-made changes show too."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import project_view
import tmp_root  # noqa: F401
from test_project_marks import git, project, using

EXPECTED_TESTS = 3


class Recent(unittest.TestCase):
    def report(self, subjects, **specs):
        root = project(**specs)
        run = git(subjects)
        with using(run):
            text = project_view.report(str(root), [], 0, None)
        return text, run

    def test_spec_commits_are_left_out_and_the_others_listed_newest_first(self):
        text, _ = self.report(["docs: newest (#9)", "feat(01-a): 01-a (#8)", "fix(x): middle (#7)",
                               "feat(lean): hand made (#6)"], **{"01-a.md": ""})
        tail = text.split("recently merged:\n")[1].splitlines()
        self.assertEqual(["  docs: newest (#9)", "  fix(x): middle (#7)", "  feat(lean): hand made (#6)"], tail)

    def test_only_the_eight_latest_are_shown(self):
        text, _ = self.report([f"fix: change {n}" for n in range(12)], **{"01-a.md": ""})
        listed = text.split("recently merged:\n")[1].splitlines()
        self.assertEqual(8, len(listed))
        self.assertEqual("  fix: change 0", listed[0])

    def test_none_or_unreadable_git_means_no_section_and_still_one_git_call(self):
        text, run = self.report(["feat(01-a): 01-a (#8)"], **{"01-a.md": ""})
        self.assertNotIn("recently merged", text)
        self.assertEqual(1, len(run.calls))
        root = project(**{"01-a.md": ""})
        with using(git([], refs=())):
            self.assertNotIn("recently merged", project_view.report(str(root), [], 0, None))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
