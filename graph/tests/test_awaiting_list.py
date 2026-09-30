"""The list shows the recorded projects that wait for a person and have no loop running, after the running
loops; the screen counts its lines as fixed and `? awaiting answer` is the mark (docs/lean/08-awaiting-you.md)."""

import calendar
import contextlib
import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops
import loops_list
import loops_projects
import project_specs
import project_view
import tmp_root  # noqa: F401
from test_project_marks import front, git, using

EXPECTED_TESTS = 13
NOW = calendar.timegm((2026, 9, 30, 9, 0, 0))
HEAD = "    PID ELAPSED COMMAND\n"
NONE = "no lean loops running"
WAITING = "waiting for you:"


def process(pid, repo):
    return f"{pid} 75 python3 graph/lean.py --workspace /none --repo {repo} --spec /s/s.md\n"


class Waiting(unittest.TestCase):
    def setUp(self):
        self.parent = pathlib.Path(tempfile.mkdtemp())
        self.recorded = []
        state = self.parent / "state"
        patched = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(state)})
        patched.start()
        self.addCleanup(patched.stop)

    def project(self, name, **specs):
        """A recorded project folder `name` whose docs/lean holds the specs (name -> lean_status or None)."""
        root = self.parent / name
        (root / "docs" / "lean").mkdir(parents=True)
        for spec, status in specs.items():
            (root / "docs" / "lean" / f"{spec}.md").write_text(front(status) if status else "Spec.\n")
        self.record(root)
        return root

    def record(self, *folders):
        self.recorded.extend(str(folder) for folder in folders)
        file = loops_projects.path()
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("".join(f"{folder}\n" for folder in self.recorded))

    def listing(self, ps="", built=("05-built",), color=False):
        with using(git([f"feat({name}): x" for name in built])):
            return loops_list.report(HEAD + ps, lambda pid: None, NOW, color)

    def test_each_kind_is_named_with_its_words_and_a_built_spec_is_not_one(self):
        self.project("shop", **{"01-asked": "questions", "02-stop": "stopped", "03-open": "pr_open",
                                "04-idle": None, "05-built": "questions"})
        self.assertEqual(f"{NONE}\n\n{WAITING}\nshop  01-asked  awaiting answer\n"
                         "shop  02-stop   stopped\nshop  03-open   pr open", self.listing())

    def test_with_nothing_waiting_the_list_is_the_single_line_it_is_today(self):
        self.project("shop", **{"01-idle": None, "02-done": "done", "05-built": "stopped"})
        self.assertEqual(NONE, self.listing())
        loops_projects.path().unlink()                                              # and with no file at all
        self.assertEqual(NONE, self.listing())

    def test_a_running_loop_a_gone_folder_and_a_folder_without_docs_lean_are_skipped(self):
        busy = self.project("busy", **{"01-asked": "questions"})
        self.project("quiet", **{"01-asked": "questions"})
        (self.parent / "bare").mkdir()
        self.record(self.parent / "bare", self.parent / "gone", "")
        listing = self.listing(process(4, busy)).splitlines()
        self.assertEqual(["1  busy   s         starting  1m15s  loop up 1m15s", "", WAITING,
                          "   quiet  01-asked  awaiting answer"], listing)

    def test_the_lines_sit_in_the_loops_columns_whichever_side_is_wider(self):
        wide = self.project("a-long-project-name", **{"01-asked": "questions"})
        busy = self.project("b", **{"01-x": None})
        lines = self.listing(process(4, busy) + process(5, wide.parent / "c")).splitlines()
        self.assertEqual(["1  b", "2  c"], [line[:4] for line in lines[:2]])
        self.assertEqual("   a-long-project-name  01-asked  awaiting answer", lines[-1])
        self.assertEqual(["s", "s", "0"], [lines[0][24], lines[1][24], lines[-1][24]])   # the spec column of every line

    def test_a_running_loop_is_told_from_its_repo_as_the_project_view_resolves_it(self):
        busy = self.project("busy", **{"01-asked": "questions"})
        link = self.parent / "link"
        link.symlink_to(busy)
        self.assertNotIn(WAITING, self.listing(process(4, f"{link}/")))

    def test_projects_go_by_folder_name_then_spec_and_a_symlink_lists_a_project_once(self):
        self.project("zed", **{"01-b": "stopped"})
        alpha = self.project("alpha", **{"02-y": "pr_open", "01-x": "questions"})
        link = self.parent / "link"
        link.symlink_to(alpha)
        self.record(link)
        self.assertEqual([WAITING, "alpha  01-x  awaiting answer", "alpha  02-y  pr open", "zed    01-b  stopped"],
                        self.listing().splitlines()[2:])

    def test_the_lines_have_the_colour_of_their_mark_and_the_heading_is_bold(self):
        self.project("shop", **{"01-asked": "questions", "02-stop": "stopped"})
        lines = self.listing(color=True).splitlines()
        self.assertEqual(["\033[1mwaiting for you:\033[0m", "\033[35mshop  01-asked  awaiting answer\033[0m",
                          "\033[31mshop  02-stop   stopped\033[0m"], lines[2:])

    def test_a_folder_name_with_trailing_spaces_is_read_as_written(self):
        odd = self.project("odd  ", **{"01-asked": "questions"})
        self.assertEqual(f"{odd}", loops_projects.folders()[0])
        self.assertIn("odd    01-asked  awaiting answer", self.listing())

    def test_ten_projects_are_ten_blocks_of_lines(self):
        for at in range(10):
            self.project(f"p{at}", **{"01-asked": "questions"})
        self.assertEqual(10, len(self.listing().splitlines()) - 3)

    def test_the_screen_and_once_print_the_block_and_the_height_counts_it(self):
        mine = self.project("mine", **{f"{at:02d}-s": None for at in range(12)})
        self.project("theirs", **{"01-asked": "questions", "02-stop": "stopped"})

        def screen(*more):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), using(git()):
                loops.main(["--screen", str(mine), *more], read_ps=lambda: HEAD + process(4, mine),
                           cwd_of=lambda pid: None, clock=lambda: NOW)
            return out.getvalue().splitlines()
        for lines in (screen("--once"), screen("--rows", "20")):
            self.assertIn("   theirs  01-asked  awaiting answer", lines)
            self.assertIn("   theirs  02-stop   stopped", lines)
        self.assertLessEqual(len(screen("--rows", "20")), 19)
        self.assertGreater(len(screen("--once")), 19)

    def test_the_mark_reads_awaiting_answer_in_the_lines_the_counts_and_the_filters(self):
        self.assertEqual("? awaiting answer", project_specs.QUESTION)
        root = self.project("shop", **{"01-a": "questions", "02-b": "stopped", "03-c": None})
        with using(git()):
            text = project_view.report(str(root), [], NOW, None).splitlines()
            attention = project_view.report(str(root), [], NOW, "attention").splitlines()
        self.assertIn("1 awaiting answer", text[0])
        self.assertEqual(["? awaiting answer  01-a", "✖ stopped          02-b"], attention[2:])
        self.assertEqual(project_view.WIDTH, len("? awaiting answer"))

    def test_reading_writes_nothing_and_starts_only_git_log(self):
        mine = self.project("mine", **{"01-asked": "questions"})
        before = sorted(str(p) for p in self.parent.rglob("*"))
        run = git()
        with using(run), mock.patch.object(pathlib.Path, "write_text", side_effect=AssertionError("wrote")), \
                mock.patch.object(pathlib.Path, "mkdir", side_effect=AssertionError("made")):
            self.assertIn(WAITING, loops_list.report(HEAD, lambda pid: None, NOW))
        self.assertEqual(before, sorted(str(p) for p in self.parent.rglob("*")))
        self.assertTrue(run.calls and all("log" in call for call in run.calls), run.calls)
        self.assertTrue(mine.is_dir())

    def test_the_new_modules_and_the_files_stay_under_the_cap(self):
        lib = pathlib.Path(loops_list.__file__).parent
        for path in (*(lib / f"{name}.py" for name in ("waiting_view", "projects_log", "loops_projects", "loops_waiting",
                                                       "loops_list")), pathlib.Path(__file__)):
            self.assertLessEqual(len(path.read_text().splitlines()), 200, path.name)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
