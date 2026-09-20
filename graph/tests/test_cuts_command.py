"""`graph-goal.py cuts`: switch a campaign's cut-review state, or show it."""

from __future__ import annotations

import collections
import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

from cli_args import build_parser
from cuts_command import command_cuts
from workspace import Workspace

EXPECTED_TESTS = 4


def _other_subcommands() -> tuple[str, ...]:
    """Every name `build_parser` wires up besides `cuts`, read from the parser
    itself — a command added there needs no matching update here."""
    blank = build_parser("graph", collections.defaultdict(lambda: None))
    [action] = [a for a in blank._subparsers._group_actions if hasattr(a, "choices")]
    return tuple(name for name in action.choices if name != "cuts")


def _campaign() -> Workspace:
    backlog_path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
    backlog_path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": []}))
    return Workspace(tempfile.mkdtemp()).init(goal="g", backlog=str(backlog_path))


def _parse(space: Workspace, *words: str):
    commands = {name: None for name in _other_subcommands()}
    commands["cuts"] = command_cuts
    return build_parser("graph", commands).parse_args(["--workspace", str(space.root), *words])


def _run(space: Workspace, *words: str) -> tuple[int, str, str]:
    args = _parse(space, *words)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = args.run(args)
    return code, out.getvalue(), err.getvalue()


class CutsCommandTest(unittest.TestCase):
    def setUp(self):
        self.space = _campaign()
        self.file = self.space.root / "cut-states.yaml"

    def test_a_state_with_a_name_is_written_with_one_history_entry(self):
        code, out, _ = _run(self.space, "cuts", "--state", "act", "--by", "NAME")
        self.assertEqual(0, code)
        self.assertIn("act", out)
        written = yaml.safe_load(self.file.read_text("utf-8"))
        self.assertEqual("act", written["state"])
        self.assertEqual(1, len(written["history"]))
        self.assertEqual(("act", "NAME"), (written["history"][0]["to"], written["history"][0]["by"]))

    def test_bare_cuts_shows_the_state_and_its_history(self):
        _run(self.space, "cuts", "--state", "act", "--by", "NAME")
        code, out, _ = _run(self.space, "cuts")
        at = yaml.safe_load(self.file.read_text("utf-8"))["history"][0]["at"]
        self.assertEqual(0, code)
        self.assertEqual(["act", f"act by NAME at {at}"], out.splitlines())

    def test_a_state_without_a_name_returns_2_and_writes_nothing(self):
        code, out, err = _run(self.space, "cuts", "--state", "act")
        self.assertEqual(2, code)
        self.assertEqual("", out)
        self.assertIn("--by", err)
        self.assertFalse(self.file.exists())
        _run(self.space, "cuts", "--state", "observe", "--by", "NAME")
        before = self.file.read_bytes()
        self.assertEqual(2, _run(self.space, "cuts", "--state", "off")[0])
        self.assertEqual(before, self.file.read_bytes())

    def test_a_state_outside_off_observe_act_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            _parse(self.space, "cuts", "--state", "on", "--by", "NAME")
        self.assertFalse(self.file.exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
