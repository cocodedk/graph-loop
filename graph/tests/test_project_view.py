"""One project's view: its lines, its filters, both forms of <which>, and that it only reads."""

import calendar
import contextlib
import io
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops
import loops_ps
import project_view
import tmp_root  # noqa: F401
from test_project_marks import front, git, project, using

NOW = calendar.timegm((2026, 9, 28, 19, 40, 0))
HEAD = "    PID ELAPSED COMMAND\n"
SPECS = {"00-a.md": "", "01-b.md": "", "02-c.md": front("stopped"), "03-d.md": front("pr_open"),
         "04-e.md": "", "lessons.md": ""}
UNREADABLE = "git history unreadable: nothing is marked built"


def process(pid, age, repo, spec, workspace="/none"):
    return f"{pid} {age} python3 graph/lean.py --workspace {workspace} --repo {repo} --spec {spec}\n"


class View(unittest.TestCase):
    def setUp(self):
        self.root = project(**SPECS)

    def show(self, which=None, only=None, ps="", run=None):
        """The status and text of `loops.py <which>`, with git faked as `run` (00-a built by default)."""
        argv = [str(self.root) if which is None else str(which)] + (["--only", only] if only else [])
        out = io.StringIO()
        with contextlib.redirect_stdout(out), using(run or git(["feat(00-a): x"])):
            code = loops.main(argv, read_ps=lambda: HEAD + ps, cwd_of=lambda pid: "/work",
                              clock=lambda: NOW)
        return code, out.getvalue()

    def report(self, only=None, running=(), run=None):
        with using(run or git(["feat(00-a): x"])):
            return project_view.report(str(self.root), list(running), NOW, only)

    def test_the_first_line_leaves_out_zero_counts_and_lines_are_aligned(self):
        self.assertEqual(f"{self.root.name}  5 specs: 1 built · 1 stopped · 1 pr open · 2 waiting\n\n"
                         "✔ built            00-a\n· waiting          01-b\n✖ stopped          02-c\n"
                         "● pr open          03-d\n· waiting          04-e", self.report())

    def test_a_running_loop_is_a_loop_line_and_the_building_mark(self):
        ps = process(7, 900, self.root, "/s/01-b.md") + process(9, 5, "/other", "/s/x.md")
        code, out = self.show(ps=ps)
        lines = out.splitlines()
        self.assertEqual(0, code)
        self.assertEqual(f"{self.root.name}  5 specs: 1 built · 1 building · 1 stopped · 1 pr open · 1 waiting",
                         lines[0])
        self.assertEqual("  loop: 01-b starting 15m00s", lines[1])
        self.assertEqual("▶ building         01-b", lines[4])

    def test_a_building_loop_line_carries_its_progress_and_other_steps_do_not(self):
        ps = process(7, 900, self.root, "/s/01-b.md")
        with mock.patch("loops_alive.progress", return_value="last step 12s ago · 186 steps"), \
                mock.patch("loops_step.step", side_effect=[("building", 60), ("reviewing", 60)]):
            self.assertIn("building 1m00s  last step 12s ago · 186 steps", self.show(ps=ps)[1])
            self.assertNotIn("last step", self.show(ps=ps)[1])

    def test_no_running_loop_has_no_loop_line(self):
        self.assertEqual("", self.report().splitlines()[1])

    def test_a_loop_that_is_both_building_and_built_shows_as_building(self):
        (loop,) = loops_ps.loops_in(process(1, 5, self.root, "/s/00-a.md"), lambda pid: None)
        self.assertIn("▶ building         00-a", self.report(running=[loop]).splitlines())

    def test_two_loops_on_one_project_come_by_process_id(self):
        ps = process(30, 60, self.root, "/s/04-e.md") + process(4, 120, f"{self.root}/", "/s/00-a.md")
        lines = self.show(ps=ps)[1].splitlines()
        self.assertEqual(["  loop: 00-a starting 2m00s", "  loop: 04-e starting 1m00s"], lines[1:3])

    def test_a_spec_name_with_spaces_or_punctuation_shows_and_matches_as_its_slug(self):
        self.root = project(**{"05 f (g).md": ""})
        out = self.show(ps=process(1, 5, self.root, "/s/05 f (g).md"))[1]
        self.assertIn("  loop: 05-f-g starting 5s", out)
        self.assertIn("▶ building         05-f-g", out)

    def test_each_filter(self):
        want = {"built": ["✔ built            00-a"],
                "open": ["· waiting          01-b", "✖ stopped          02-c", "● pr open          03-d",
                         "· waiting          04-e"],
                "attention": ["✖ stopped          02-c", "● pr open          03-d"]}
        for only, lines in want.items():
            with self.subTest(only=only):
                shown = self.report(only).splitlines()
                self.assertEqual(lines, shown[2:])
                self.assertIn("5 specs: 1 built", shown[0])        # the counts cover every spec

    def test_a_filter_that_matches_nothing_and_a_project_without_specs(self):
        self.root = project(**{"a.md": ""})
        self.assertEqual(f"{self.root.name}  1 specs: 1 waiting\n\nno specs match", self.report("attention"))
        self.root = project(**{"lessons.md": ""})
        for only in (None, "built", "open", "attention"):
            with self.subTest(only=only):
                self.assertEqual(f"{self.root.name}  0 specs\n\nno specs", self.report(only))

    def test_a_filter_outside_the_three_is_refused_with_usage_and_status_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            loops.main([str(self.root), "--only", "all"], read_ps=lambda: HEAD)
        self.assertEqual(2, caught.exception.code)
        self.assertIn("usage: loops.py", err.getvalue())

    def test_unreadable_git_falls_back_to_the_front_matter_and_says_so(self):
        lines = self.report(run=git(refs=())).splitlines()
        self.assertEqual(UNREADABLE, lines[1])
        self.assertEqual(["· waiting          00-a", "· waiting          01-b", "✖ stopped          02-c",
                          "● pr open          03-d", "· waiting          04-e"], lines[3:])
        self.assertEqual(0, self.show(run=git(refs=()))[0])

    def test_the_unreadable_git_line_follows_the_loop_lines(self):
        loop = loops_ps.loops_in(process(1, 5, self.root, "/s/00-a.md"), lambda pid: None)
        lines = self.report(running=loop, run=git(refs=())).splitlines()
        self.assertEqual(["  loop: 00-a starting 5s", UNREADABLE], lines[1:3])

    def test_a_number_from_the_list_names_the_project_of_that_loop(self):
        ps = process(30, 60, "/elsewhere", "/s/x.md") + process(40, 60, self.root, "/s/00-a.md")
        code, out = self.show(2, ps=ps)
        self.assertEqual(0, code)
        self.assertIn("▶ building         00-a", out)

    def test_a_number_outside_the_list(self):
        for number in (0, 3):
            with self.subTest(number=number):
                self.assertEqual((2, f"no loop number {number}\n"),
                                 self.show(number, ps=process(1, 5, self.root, "/s/a.md")))

    def test_a_path_that_is_not_a_project_folder(self):
        for path in (self.root / "docs" / "lean" / "01-b.md", self.root / "missing", self.root.parent):
            with self.subTest(path=path):
                self.assertEqual((2, f"not a project with docs/lean: {path}\n"), self.show(path))

    def test_a_number_whose_repo_has_no_docs_lean(self):
        self.assertEqual((2, "not a project with docs/lean: /no/such/repo\n"),
                         self.show(1, ps=process(1, 5, "/no/such/repo", "/s/a.md")))

    def test_the_command_writes_nothing(self):
        def snapshot():
            return {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}, sorted(self.root.rglob("*"))
        before = snapshot()
        with mock.patch.object(pathlib.Path, "write_text", side_effect=AssertionError("wrote")), \
                mock.patch.object(pathlib.Path, "write_bytes", side_effect=AssertionError("wrote")):
            self.assertEqual(0, self.show()[0])
        self.assertEqual(before, snapshot())

    def test_a_real_git_repository_is_read(self):
        real = subprocess.run     # the fake is stood in by `show`, so hand it the real call
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for command in (["init", "-q", "-b", "main"],
                        ["-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "feat(01-b): y"]):
            real(["git", "-C", str(self.root), *command], env=env, check=True, capture_output=True)
        self.assertIn("✔ built            01-b", self.show(run=real)[1])


class Size(unittest.TestCase):
    def test_every_file_of_the_view_is_under_the_cap(self):
        graph = pathlib.Path(__file__).resolve().parents[1]
        files = [graph / "loops.py", graph / "lib" / "project_specs.py", graph / "lib" / "project_view.py",
                 graph / "lib" / "project_cost.py", graph / "lib" / "loops_ps.py",
                 *pathlib.Path(__file__).parent.glob("test_project_*.py")]
        self.assertEqual(8, len(files))
        for path in files:
            with self.subTest(path=path.name):
                self.assertLessEqual(len(path.read_text("utf-8").splitlines()), 200)


EXPECTED_TESTS = 19


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
