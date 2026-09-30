"""`loops.py --color` (docs/lean/06-colours.md): the same text with ANSI codes, which say what needs a look."""

import calendar
import contextlib
import io
import json
import pathlib
import re
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops
import loops_alive
import loops_list
import project_view
import test_loops_alive
import tmp_root  # noqa: F401
from test_project_cost import build, started, write
from test_project_marks import front, git, project, using

EXPECTED_TESTS = 9
NOW = calendar.timegm((2026, 9, 28, 19, 40, 0))
HEAD = "    PID ELAPSED COMMAND\n"
SPECS = {"01-built.md": "", "02-run.md": "", "03-stop.md": front("stopped"), "04-ask.md": front("questions"),
         "05-pr.md": front("pr_open"), "06-wait.md": ""}
COSTS = {"01-built": 3.99, "03-stop": 3.991, "04-ask": 8.001, "05-pr": 8.0, "06-wait": 9.0}   # cents are shown rounded, judged whole
TESTING = {"kind": "attempt", "purpose": "build"}


def esc(code, text):
    return f"\033[{code}m{text}\033[0m"


def strip(text):
    return re.sub(r"\033\[[0-9;]*m", "", text)


def make():
    """A project of SPECS whose log holds COSTS, and for 01-built also its turns, model and day."""
    root = project(**SPECS)
    rows = [row for name, cost in COSTS.items() for row in (started(name), {**build(name, cost), "turns": 12})]
    write(root, "events.jsonl", [*rows, {"kind": "lean_call_started", "purpose": "build", "task": "01-built",
                                          "model": "claude-sonnet-5-5"},
                                 {"kind": "lean_published", "task": "01-built", "at": "2026-09-30T07:33:21Z"}])
    return root


def ps_of(root, row=None, seconds=0):
    """One loop, building 02-run of `root`, whose log ends with the event `row`, `seconds` old."""
    workspace = pathlib.Path(tempfile.mkdtemp())
    if row:
        at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - seconds))
        (workspace / "events.jsonl").write_text(json.dumps({**row, "at": at}) + "\n")
    return f"7 75 python3 graph/lean.py --workspace {workspace} --repo {root} --spec /s/02-run.md\n"


def run(ps, *argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), using(git(["feat(01-built): x", "docs: by hand"])):
        code = loops.main(list(argv), read_ps=lambda: HEAD + ps, cwd_of=lambda pid: "/work", clock=lambda: NOW)
    return code, out.getvalue()


def line_of(out, name):
    """The last line that names `name`: the spec's own, after the loop line of a running one."""
    return next(line for line in reversed(out.splitlines()) if name in strip(line))


class Colours(unittest.TestCase):
    def setUp(self):
        self.root = make()
        self.ps = ps_of(self.root, TESTING, 900)
        self.what = ([], [str(self.root)], ["--screen", str(self.root)], ["--screen", str(self.root), "--rows", "9"],
                     [str(self.root), "--only", "open"])

    def test_stripping_the_codes_leaves_the_text_without_them(self):
        for argv in self.what:
            with self.subTest(argv=argv):
                plain, colour = run(self.ps, *argv), run(self.ps, *argv, "--color")
                self.assertEqual(0, plain[0])
                self.assertNotEqual(plain, colour)
                self.assertEqual(plain, (colour[0], strip(colour[1])))

    def test_without_the_option_there_is_no_escape_anywhere(self):
        for argv in self.what:
            with self.subTest(argv=argv):
                self.assertNotIn("\033", run(self.ps, *argv)[1])
        self.assertNotIn("\033", run(self.ps, "--screen", str(self.root), "--once")[1])

    def test_each_mark_carries_its_colour_and_a_waiting_line_is_dim_whole(self):
        out = run(self.ps, str(self.root), "--color")[1]
        for name, mark, code in (("01-built", "✔ built", 32), ("02-run", "▶ building", 33), ("03-stop", "✖ stopped", 31),
                                 ("04-ask", "? awaiting answer", 35), ("05-pr", "● pr open", 36)):
            self.assertTrue(line_of(out, name).startswith(esc(code, mark)), name)
        waiting = line_of(out, "06-wait")
        self.assertEqual(esc(2, strip(waiting)), waiting)

    def test_a_cost_is_yellow_above_3_99_and_red_above_8_and_plain_otherwise(self):
        out = run(self.ps, str(self.root), "--color")[1]
        for name, text, code in (("01-built", "$3.99", None), ("03-stop", "$3.99", 33), ("05-pr", "$8.00", 33),
                                 ("04-ask", "$8.00", 31)):
            with self.subTest(name=name):
                line = line_of(out, name)
                if code:
                    self.assertIn(esc(code, text), line)
                else:
                    self.assertIn(f"  {text}", line)
                    self.assertNotIn(f"m{text}", line)

    def test_the_day_the_turns_and_the_model_are_dim(self):
        line = line_of(run(self.ps, str(self.root), "--color")[1], "01-built")
        self.assertTrue(line.endswith(f"  {esc(2, '2026-09-30')}  {esc(2, '12t')}  {esc(2, 'sonnet-5-5')}"))

    def test_the_first_line_and_the_loop_name_are_bold_the_key_line_and_the_merged_ones_dim(self):
        plain = run(self.ps, "--screen", str(self.root))[1].splitlines()
        lines = run(self.ps, "--screen", str(self.root), "--color")[1].splitlines()
        first = next(at for at, line in enumerate(plain) if "6 specs" in line)
        self.assertEqual(esc(1, plain[first]), lines[first])
        self.assertEqual(f"{esc(1, '  loop: 02-run')} {esc(31, 'testing 15m00s')}", lines[first + 1])
        self.assertEqual(esc(2, plain[-1]), lines[-1])
        self.assertEqual([esc(1, "recently merged:"), esc(2, "  docs: by hand")],
                         lines[lines.index(esc(1, "recently merged:")):][:2])

    def test_a_shrink_line_takes_the_colour_of_its_mark(self):
        root = project(**{f"0{at}-{name}.md": "" for at, name in enumerate("abcdefghij", 1)})
        with using(git([f"feat(0{at}-{name}): x" for at, name in enumerate("abcdef", 1)])):
            lines = project_view.report(str(root), [], NOW, None, 6, True).splitlines()
        self.assertIn(esc(32, "✔ built            … 6 more"), lines)
        self.assertIn(esc(2, "· waiting          … 2 more"), lines)

    def test_the_step_takes_the_thresholds_in_the_list_and_red_from_15_minutes_in_the_view_when_testing_or_checking(self):
        for row, step in ((TESTING, "testing"), ({"kind": "lean_published"}, "checking the build"),
                          ({"kind": "lean_call_started", "purpose": "build"}, "building")):
            for seconds, listed_code in ((299, None), (300, 33), (899, 33), (900, 31)):
                said = f"{step} {loops_list.duration(seconds)}"
                view_code = 31 if seconds >= 900 and step != "building" else None
                ps = ps_of(self.root, row, seconds)
                with self.subTest(step=step, seconds=seconds), mock.patch("loops_alive.progress", return_value=""):
                    lines = run(ps, str(self.root), "--color")[1].splitlines()
                    self.assertEqual(f"{esc(1, '  loop: 02-run')} {esc(view_code, said) if view_code else said}", lines[1])
                    listed = run(ps, "--color")[1]
                    self.assertEqual(listed_code, next((code for code in (31, 33) if esc(code, step) in listed), None))
                    self.assertTrue(listed.rstrip("\n").endswith(esc(2, "loop up 1m15s")))


class Quiet(unittest.TestCase):
    setUp, process, write = test_loops_alive.Alive.setUp, test_loops_alive.Alive.process, test_loops_alive.Alive.write

    def test_last_step_ago_takes_the_thresholds_at_their_edges(self):
        for age, code, words in ((299, None, "4m59s"), (300, 33, "5m00s"), (899, 33, "14m59s"), (900, 31, "15m00s")):
            with self.subTest(age=age):
                self.write(3, age)
                said = f"last step {words} ago"
                self.assertEqual(f"{esc(code, said) if code else said} · 3 steps",
                                 loops_alive.progress(100, test_loops_alive.NOW, str(self.proc), color=True))
                self.assertEqual(f"{said} · 3 steps", loops_alive.progress(100, test_loops_alive.NOW, str(self.proc)))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
