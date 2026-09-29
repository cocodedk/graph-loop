"""The live screen's Python: `--screen`, `--path`, `--once` and `--refresh` of loops.py."""

import calendar
import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops
import loops_list
import loops_ps
import project_view
import test_loops_list
import tmp_root  # noqa: F401
from test_project_marks import git, project, using

NOW = calendar.timegm((2026, 9, 28, 19, 40, 0))
HEAD = "    PID ELAPSED COMMAND\n"
NONE = "no lean loops running"


def key_line(only="all", refresh=15):
    return f"keys: 1-9 switch loop · f filter ({only}) · q quit · every {refresh}s"


def process(pid, repo):
    return f"{pid} 75 python3 graph/lean.py --workspace /none --repo {repo} --spec /s/s.md\n"


class Screen(unittest.TestCase):
    def setUp(self):
        self.root = project(**{"00-a.md": "", "01-b.md": ""})

    def run_loops(self, *argv, ps="", cwd=lambda pid: None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), using(git(["feat(00-a): x"])):
            code = loops.main(list(argv), read_ps=lambda: HEAD + ps, cwd_of=cwd, clock=lambda: NOW)
        return code, out.getvalue()

    def view(self, only=None, running=()):
        with using(git(["feat(00-a): x"])):
            return project_view.report(str(self.root), list(running), NOW, only)

    def listing(self, ps):
        return loops_list.report(HEAD + ps, lambda pid: None, NOW)

    def test_a_given_folder_shows_the_list_the_view_and_the_key_line_in_order(self):
        ps = process(5, "/other/repo")
        code, out = self.run_loops("--screen", str(self.root), ps=ps)
        self.assertEqual(0, code)
        self.assertEqual("1  repo  s  starting  1m15s  loop up 1m15s\n\n" + self.view() + "\n\n"
                         + key_line() + "\n", out)

    def test_no_folder_given_shows_the_first_running_loop_whose_folder_can_be_resolved(self):
        ps = process(1, "../unresolved") + process(2, self.root) + process(3, "/other/repo")
        code, out = self.run_loops("--screen", ps=ps)
        (_, mine, _) = loops_ps.loops_in(HEAD + ps, lambda pid: None)
        self.assertEqual(0, code)
        self.assertEqual(self.listing(ps) + "\n\n" + self.view(running=[mine]) + "\n\n" + key_line() + "\n", out)
        self.assertTrue(out.startswith("1  ?  "))

    def test_no_folder_and_no_loop_shows_only_the_message_and_the_key_line(self):
        self.assertEqual((0, f"{NONE}\n\n{key_line()}\n"), self.run_loops("--screen"))

    def test_a_loop_whose_folder_cannot_be_resolved_leaves_no_view_to_show(self):
        ps = process(1, "../unresolved")
        self.assertEqual((0, self.listing(ps) + f"\n\n{key_line()}\n"), self.run_loops("--screen", ps=ps))

    def test_the_filter_reaches_the_view_and_the_key_line(self):
        code, out = self.run_loops("--screen", str(self.root), "--only", "built")
        self.assertEqual((0, f"{NONE}\n\n{self.view('built')}\n\n{key_line('built')}\n"), (code, out))
        self.assertNotIn("01-b", out)
        self.assertIn(key_line("attention"), self.run_loops("--screen", "--only", "attention")[1])

    def test_the_key_line_says_the_refresh_it_is_given(self):
        self.assertIn(key_line(refresh=3), self.run_loops("--screen", "--refresh", "3")[1])
        self.assertIn(key_line(refresh="0.5"), self.run_loops("--screen", "--refresh", "0.5")[1])

    def test_once_leaves_out_the_key_line_and_the_blank_line_before_it(self):
        ps = process(2, self.root)
        (mine,) = loops_ps.loops_in(HEAD + ps, lambda pid: None)
        self.assertEqual((0, self.listing(ps) + "\n\n" + self.view(running=[mine]) + "\n"),
                         self.run_loops("--screen", "--once", ps=ps))
        self.assertEqual((0, f"{NONE}\n\n{self.view()}\n"),
                         self.run_loops("--screen", str(self.root), "--once"))
        self.assertEqual((0, f"{NONE}\n"), self.run_loops("--screen", "--once"))

    def test_a_folder_that_is_not_a_project_takes_the_place_of_the_view(self):
        nope = str(self.root / "nope")
        self.assertEqual((0, f"{NONE}\n\nnot a project with docs/lean: {nope}\n\n{key_line()}\n"),
                         self.run_loops("--screen", nope))

    def test_path_prints_the_folder_of_that_loop_or_nothing(self):
        ps = process(10, self.root) + process(20, "/other/repo")
        for number, expected in (("1", f"{self.root}\n"), ("2", "/other/repo\n"), ("3", ""), ("0", "")):
            with self.subTest(number=number):
                self.assertEqual((0, expected), self.run_loops("--path", number, ps=ps))
        self.assertEqual((0, ""), self.run_loops("--path", "1", ps=process(1, "../unresolved")))
        self.assertEqual((0, ""), self.run_loops("--path", "1"))

    def test_a_failing_ps_is_told_for_the_screen_and_for_the_path(self):
        def broken():
            raise loops_ps.PsError("no ps")
        for argv in (["--screen"], ["--screen", str(self.root), "--once"], ["--path", "1"]):
            with self.subTest(argv=argv):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = loops.main(argv, read_ps=broken)
                self.assertEqual((1, "cannot read the process list\n"), (code, out.getvalue()))

    def test_the_screen_and_the_path_write_nothing(self):
        ps = process(2, self.root)
        with mock.patch.object(pathlib.Path, "write_text", side_effect=AssertionError("wrote")), \
                mock.patch("builtins.open", side_effect=test_loops_list.Listing.no_writing(open)):
            self.assertEqual(0, self.run_loops("--screen", ps=ps)[0])
            self.assertEqual(0, self.run_loops("--path", "1", ps=ps)[0])


class Size(unittest.TestCase):
    def test_the_script_and_its_python_are_under_the_cap(self):
        graph = pathlib.Path(__file__).resolve().parents[1]
        for path in (graph / "loops.py", graph / "lib" / "screen_view.py", graph / "loops.sh"):
            with self.subTest(path=path.name):
                self.assertLessEqual(len(path.read_text("utf-8").splitlines()), 200)


EXPECTED_TESTS = 12


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
