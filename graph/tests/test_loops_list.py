"""The list of running lean loops: its lines, its failures, and that it only reads."""

import calendar
import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops
import loops_ps
import tmp_root  # noqa: F401

NOW = calendar.timegm((2026, 9, 28, 19, 40, 0))
HEAD = "    PID ELAPSED COMMAND\n"


def process(pid, age, repo, spec, workspace):
    return f"{pid} {age} python3 graph/lean.py --workspace {workspace} --repo {repo} --spec {spec}\n"


class Listing(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())

    def workspace(self, name, *lines):
        path = self.root / name
        path.mkdir()
        (path / "events.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
        return str(path)

    def run_loops(self, text, cwd_for=lambda pid: "/work"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = loops.main([], read_ps=lambda: text, cwd_of=cwd_for, clock=lambda: NOW)
        return code, out.getvalue()

    def two(self):
        grilling = self.workspace("a", {"at": "2026-09-28T19:37:50Z", "kind": "lean_call_started",
                                        "purpose": "grill"})
        building = self.workspace("b", {"at": "2026-09-28T19:27:57Z", "kind": "lean_call_started",
                                        "purpose": "build"})
        return (HEAD + process(220, 2700, "/r/fits-api", "/s/02f-routes.md", building)
                + process(90, 1860, "/r/sitrep", "/s/01-capture-core.md", grilling))

    def test_two_loops_are_numbered_by_process_id_and_padded_to_their_longest_value(self):
        code, out = self.run_loops(self.two())
        self.assertEqual(0, code)
        self.assertEqual("1  sitrep    01-capture-core  grilling  2m10s   loop up 31m00s\n"
                         "2  fits-api  02f-routes       building  12m03s  loop up 45m00s\n", out)

    def test_ten_loops_widen_the_number_column(self):
        text = HEAD + "".join(process(pid, 5, "/r/p", "s.md", "/none") for pid in range(1, 11))
        lines = self.run_loops(text)[1].splitlines()
        self.assertEqual("1   p  s  starting  5s  loop up 5s", lines[0])
        self.assertEqual("10  p  s  starting  5s  loop up 5s", lines[9])

    def test_a_loop_whose_workspace_cannot_be_read_still_appears_as_starting(self):
        text = HEAD + process(7, 75, "/r/sitrep", "/s/a.md", "/no/such/workspace")
        self.assertEqual("1  sitrep  a  starting  1m15s  loop up 1m15s\n", self.run_loops(text)[1])

    def test_no_loops_running(self):
        self.assertEqual((0, "no lean loops running\n"), self.run_loops(HEAD + "1 5 bash\n"))
        self.assertEqual((0, "no lean loops running\n"), self.run_loops(""))

    def test_an_unreadable_working_directory_with_an_absolute_and_a_relative_repo(self):
        text = (HEAD + process(1, 5, "/r/sitrep", "a.md", "/w") + process(2, 5, "../sitrep", "b.md", "/w"))
        lines = self.run_loops(text, cwd_for=lambda pid: None)[1].splitlines()
        self.assertEqual(["1  sitrep  a  starting  5s  loop up 5s",
                          "2  ?       b  starting  5s  loop up 5s"], lines)

    def test_a_relative_workspace_is_read_from_the_working_directory(self):
        (self.root / "ws").mkdir()
        (self.root / "ws" / "events.jsonl").write_text(
            json.dumps({"at": "2026-09-28T19:39:15Z", "kind": "lean_suite"}) + "\n")
        text = HEAD + process(1, 900, "/r/p", "s.md", "ws")
        self.assertEqual("1  p  s  working  45s  loop up 15m00s\n",
                         self.run_loops(text, cwd_for=lambda pid: str(self.root))[1])

    def test_a_failing_ps_is_told_and_exits_1(self):
        def broken():
            raise loops_ps.PsError("no ps")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = loops.main([], read_ps=broken)
        self.assertEqual((1, "cannot read the process list\n"), (code, out.getvalue()))

    def test_ps_that_cannot_run_or_exits_non_zero_is_a_ps_error(self):
        with mock.patch.object(loops_ps.subprocess, "run", side_effect=FileNotFoundError("ps")):
            with self.assertRaises(loops_ps.PsError):
                loops_ps.read_ps()
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="boom")
        with mock.patch.object(loops_ps.subprocess, "run", return_value=failed):
            with self.assertRaises(loops_ps.PsError):
                loops_ps.read_ps()

    def test_ps_is_asked_for_pid_etimes_and_args(self):
        done = subprocess.CompletedProcess([], 0, stdout="listing", stderr="")
        with mock.patch.object(loops_ps.subprocess, "run", return_value=done) as run:
            self.assertEqual("listing", loops_ps.read_ps())
        self.assertEqual(["ps", "-eo", "pid,etimes,args"], run.call_args.args[0])

    def test_the_command_writes_nothing_and_exits_0(self):
        text = self.two()
        before = sorted(str(p) for p in self.root.rglob("*")), {
            p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        here = pathlib.Path(tempfile.mkdtemp())
        with mock.patch.object(pathlib.Path, "write_text", side_effect=AssertionError("wrote")), \
                mock.patch("builtins.open", side_effect=self.no_writing(open)):
            cwd = os.getcwd()
            os.chdir(here)
            try:
                code, _ = self.run_loops(text)
            finally:
                os.chdir(cwd)
        after = sorted(str(p) for p in self.root.rglob("*")), {
            p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(0, code)
        self.assertEqual(before, after)
        self.assertEqual([], list(here.iterdir()))

    def test_a_fresh_checkout_gets_no_bytecode_files_from_a_run(self):
        graph = pathlib.Path(loops.__file__).resolve().parent
        copy = pathlib.Path(tempfile.mkdtemp()) / "graph"
        (copy / "lib").mkdir(parents=True)
        for path in (graph / "loops.py", *(graph / "lib").glob("loops_*.py")):
            (copy / path.relative_to(graph)).write_text(path.read_text("utf-8"))
        fake = pathlib.Path(tempfile.mkdtemp()) / "ps"    # a ps that lists no process
        fake.write_text("#!/bin/sh\nprintf '    PID ELAPSED COMMAND\\n'\n")
        fake.chmod(0o755)
        env = {key: value for key, value in os.environ.items()
               if key not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
        env["PATH"] = f"{fake.parent}{os.pathsep}{env.get('PATH', '')}"
        before = sorted(str(p) for p in copy.rglob("*"))
        done = subprocess.run([sys.executable, str(copy / "loops.py")], cwd=copy, env=env,
                              capture_output=True, text=True, check=False)
        self.assertEqual((0, "no lean loops running\n"), (done.returncode, done.stdout))
        self.assertEqual(before, sorted(str(p) for p in copy.rglob("*")))

    @staticmethod
    def no_writing(real_open):
        def guarded(file, mode="r", *args, **kwargs):
            if set(mode) & set("wax+"):
                raise AssertionError(f"wrote {file}")
            return real_open(file, mode, *args, **kwargs)
        return guarded


class Size(unittest.TestCase):
    def test_the_entry_and_its_modules_are_under_the_cap(self):
        graph = pathlib.Path(__file__).resolve().parents[1]
        files = [graph / "loops.py", *sorted((graph / "lib").glob("loops_*.py"))]
        self.assertEqual(4, len(files))
        for path in files:
            with self.subTest(path=path.name):
                self.assertLessEqual(len(path.read_text("utf-8").splitlines()), 200)

    def test_the_entry_file_holds_no_logic_beyond_arguments_and_printing(self):
        source = (pathlib.Path(loops.__file__)).read_text("utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("json", source)


EXPECTED_TESTS = 13


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
