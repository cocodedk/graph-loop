"""`loops.py --screen --rows N`: the project view shrinks so the screen fits the terminal."""

import calendar
import contextlib
import io
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops
import project_view
import tmp_root  # noqa: F401
from project_specs import BUILDING, PR_OPEN, QUESTION, STOPPED, WAITING
from test_project_marks import front, git, project, using

NOW = calendar.timegm((2026, 9, 28, 19, 40, 0))
HEAD = "    PID ELAPSED COMMAND\n"
UNREADABLE = "git history unreadable: nothing is marked built"


def built_more(count):
    return f"✔ built            … {count} more"


def waiting_more(count):
    return f"· waiting          … {count} more"


def spec(mark, name):
    return f"{mark.ljust(17)}  {name}"


def make(built=0, waiting=0, attention=(), **more):
    """A project of `built` built specs, then one spec per status in `attention`, then `waiting`
    waiting ones (00-built, ..., NN-stopped, ..., NN-wait); its git subjects say what is built."""
    files, subjects = dict(more), []
    for i in range(built):
        files[f"{i:02d}-built.md"] = ""
        subjects.append(f"feat({i:02d}-built): x")
    for i, status in enumerate(attention, built):
        files[f"{i:02d}-{status}.md"] = front(status)
    first = built + len(attention)
    for i in range(first, first + waiting):
        files[f"{i:02d}-wait.md"] = ""
    return project(**files), subjects


def view(root, subjects, budget, only=None, run=None):
    """The lines of the project view for a budget of that many lines (None: no shrinking)."""
    with using(run or git(subjects)):
        return project_view.report(str(root), [], NOW, only, budget).splitlines()


def screen(root, subjects, *argv, ps=""):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), using(git(subjects)):
        code = loops.main(list(argv), read_ps=lambda: HEAD + ps, cwd_of=lambda pid: None, clock=lambda: NOW)
    return code, out.getvalue()


class Fit(unittest.TestCase):
    def test_the_screen_takes_at_most_rows_minus_one_lines_and_keeps_what_needs_a_look(self):
        root, subjects = make(built=15, waiting=21, attention=("stopped", "questions", "pr_open"),
                              **{"18-build.md": ""})
        ps = f"1 75 python3 graph/lean.py --workspace /none --repo {root} --spec /s/18-build.md\n"
        code, out = screen(root, subjects, "--screen", str(root), "--rows", "30", ps=ps)
        lines = out.splitlines()
        self.assertEqual((0, 29), (code, len(lines)))
        for line in (spec(STOPPED, "15-stopped"), spec(QUESTION, "16-questions"),
                     spec(PR_OPEN, "17-pr_open"), spec(BUILDING, "18-build")):
            self.assertIn(line, lines)
        self.assertIn(built_more(15), lines)
        self.assertIn(waiting_more(5), lines)
        self.assertEqual([f"{i}-wait" for i in range(18, 34)], [line.split()[-1] for line in lines if "-wait" in line])
        self.assertTrue(lines[-1].startswith("keys: "))

    def test_built_is_one_line_and_waiting_keep_file_order_up_to_the_room(self):
        root, subjects = make(built=5, waiting=6, attention=("stopped",))
        lines = view(root, subjects, 9)
        self.assertEqual(9, len(lines))
        self.assertEqual([spec(STOPPED, "05-stopped"), built_more(5),
                          *(spec(WAITING, f"{i:02d}-wait") for i in range(6, 10)), waiting_more(2)], lines[2:])
        lines = view(root, subjects, 10)
        self.assertEqual(10, len(lines))
        self.assertEqual([spec(STOPPED, "05-stopped"), built_more(5),
                          *(spec(WAITING, f"{i:02d}-wait") for i in range(6, 12))], lines[2:])

    def test_no_built_line_when_nothing_is_built_and_no_waiting_line_when_none_wait(self):
        root, subjects = make(waiting=6, attention=("stopped",))
        lines = view(root, subjects, 6)
        self.assertEqual([spec(STOPPED, "00-stopped"), spec(WAITING, "01-wait"), spec(WAITING, "02-wait"),
                          waiting_more(4)], lines[2:])
        self.assertFalse(any("✔" in line for line in lines))
        root, subjects = make(built=5, attention=("stopped",))
        self.assertEqual([spec(STOPPED, "05-stopped"), built_more(5)], view(root, subjects, 5)[2:])

    def test_recently_merged_goes_first_and_stays_when_it_fits(self):
        root, subjects = make(built=2, waiting=2)
        subjects += ["docs: one", "docs: two", "docs: three"]
        whole = view(root, subjects, None)
        self.assertEqual(11, len(whole))
        self.assertEqual(whole, view(root, subjects, 11))
        self.assertIn("recently merged:", whole)
        self.assertEqual(whole[:6], view(root, subjects, 10))
        shrunk = view(root, subjects, 5)
        self.assertEqual([built_more(2), spec(WAITING, "02-wait"), spec(WAITING, "03-wait")], shrunk[2:])
        self.assertNotIn("recently merged:", shrunk)

    def test_what_needs_a_look_all_prints_even_when_it_is_taller_than_the_screen(self):
        root, subjects = make(built=3, waiting=3, attention=("stopped", "questions", "pr_open"))
        lines = view(root, subjects, 3)
        self.assertEqual([spec(STOPPED, "03-stopped"), spec(QUESTION, "04-questions"),
                          spec(PR_OPEN, "05-pr_open"), built_more(3), waiting_more(3)], lines[2:])
        root, subjects = make(built=2, waiting=2, attention=("stopped",))
        self.assertEqual([spec(STOPPED, "02-stopped"), built_more(2), waiting_more(2)],
                         view(root, subjects, 3)[2:])                      # exactly full: two lines taller
        root, subjects = make(waiting=2, attention=("stopped",))
        self.assertEqual(4, len(view(root, subjects, 3)))                  # no built line: one line taller

    def test_when_the_fixed_parts_overflow_only_the_two_count_lines_remain_of_the_optional_ones(self):
        root, subjects = make(built=2, waiting=2, attention=("stopped",))
        _, out = screen(root, subjects + ["docs: one"], "--screen", str(root), "--rows", "1")
        lines = out.splitlines()
        self.assertEqual([spec(STOPPED, "02-stopped"), built_more(2), waiting_more(2), "", lines[-1]], lines[4:])
        self.assertNotIn("recently merged:", out)
        self.assertNotIn("-wait", out)

    def test_the_messages_are_fixed_lines_nothing_gives_way_to(self):
        root, subjects = make()
        self.assertEqual(["", "no specs"], view(root, subjects, 0)[1:])
        self.assertEqual(6, len(view(root, subjects + ["docs: one"], 6)))  # merged fits beside it
        self.assertEqual(3, len(view(root, subjects + ["docs: one"], 5)))  # merged gives way
        root, subjects = make(waiting=2)
        self.assertEqual(["", "no specs match"], view(root, subjects, 0, "built")[1:])
        root, subjects = make(waiting=4, attention=("stopped",))
        lines = view(root, [], 3, run=git(refs=()))
        self.assertEqual([UNREADABLE, "", spec(STOPPED, "00-stopped"), waiting_more(4)], lines[1:])

    def test_the_filter_counts_only_the_specs_it_passes(self):
        root, subjects = make(built=4, waiting=6, attention=("stopped",))
        self.assertEqual(view(root, subjects, None, "open"), view(root, subjects, 9, "open"))
        self.assertEqual(view(root, subjects, None, "built"), view(root, subjects, 6, "built"))
        lines = view(root, subjects, 6, "open")
        self.assertEqual([spec(STOPPED, "04-stopped"), spec(WAITING, "05-wait"), spec(WAITING, "06-wait"),
                          waiting_more(4)], lines[2:])

    def test_without_rows_and_with_once_the_output_is_what_it_was(self):
        root, subjects = make(built=3, waiting=3, attention=("stopped",))
        plain = screen(root, subjects, "--screen", str(root))[1]
        self.assertIn("\n".join(view(root, subjects, None)), plain)
        self.assertEqual(plain, screen(root, subjects, "--screen", str(root), "--rows", "99")[1])
        self.assertNotEqual(plain, screen(root, subjects, "--screen", str(root), "--rows", "3")[1])
        once = screen(root, subjects, "--screen", str(root), "--once")
        self.assertEqual(once, screen(root, subjects, "--screen", str(root), "--once", "--rows", "3"))
        self.assertEqual(screen(root, subjects, str(root)), screen(root, subjects, str(root), "--rows", "3"))


EXPECTED_TESTS = 9


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
