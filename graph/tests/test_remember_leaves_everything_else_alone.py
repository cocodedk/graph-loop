"""`remember` is a command, not a step: it reads, and the only thing it writes
is a relative.

The node is never touched, not even its front matter; the backlog reads back
exactly as it did; the campaign log gains no event of its own; nothing the
driver, the supervisor or a hook runs so much as names it. And a log it cannot
make sense of is counted and stepped over, never raised on — a memory note is
worth less than the campaign it describes.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import io
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import backlog_tree
import cardfile
import remember
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]
from cli_args import build_parser
from workspace import Workspace

EXPECTED_TESTS = 9

# Reaching the command is importing its module or calling it, by name. The bare
# word is ordinary English and half the loop uses it about something else.
REACHES = re.compile(r"(?m)^\s*(?:from|import) +remember\b|command_remember"
                     r"|goal\.py[^\n]*\bremember\b")


def vault() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    piece = root / "T30"
    piece.mkdir(parents=True)
    (piece / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced", "note": "leave me alone"}),
        "utf-8")
    (piece / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    return root


def bytes_of(root: pathlib.Path) -> dict:
    return {str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob("*.md"))}


def good() -> list[dict]:
    return [
        {"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
         "added": ["T30", "T30.schema"]},
        {"at": "2026-09-20T07:05:30Z", "kind": "step", "task": "T30.schema",
         "step": "gate", "seconds": 8.25, "passed": True, "code": 0},
    ]


def strange() -> list[dict]:
    """Everything a log can hold that this command was never told about."""
    return [
        ["not", "a", "mapping"],
        "not a mapping either",
        {"at": "2026-09-20T06:57:00Z", "kind": "log_truncated", "bytes": 88,
         "text": "{\"at\": \"2026-09-2", "why": "a crash cut this line mid-write"},
        {"kind": "planned", "task": "the plan", "added": ["T30.schema"]},
        {"at": "2026-09-20T07:00:00Z"},
        {"at": "2026-09-20T07:00:01Z", "kind": "moon_phase", "task": "T30.schema"},
        {"at": "2026-09-20T07:00:02Z", "kind": "attempt", "task": ["T30.schema"]},
        {"at": "2026-09-20T07:00:03Z", "kind": "planned", "task": "the plan",
         "added": "T30.schema"},
        {"at": "2026-09-20T07:00:04Z", "kind": "step", "task": "T30.schema",
         "step": "gate"},
        {"at": "2026-09-20T07:00:05Z", "kind": "accepted", "task": "T30.schema"},
        {"at": "2026-09-20T07:00:06Z", "kind": "planned", "task": "the plan",
         "added": ["a-card-this-backlog-never-heard-of"]},
    ]


class TheNodeIsNeverTouched(unittest.TestCase):
    def test_not_one_card_file_changes_a_byte(self):
        root = vault()
        before = bytes_of(root)
        remember.write_memory(root, good())
        after = {name: raw for name, raw in bytes_of(root).items()
                 if "relatives" not in name}
        self.assertEqual(before, after)

    def test_the_backlog_reads_back_exactly_as_it_did(self):
        root = vault()
        before = backlog_tree.read(root)
        remember.write_memory(root, good())
        self.assertEqual(before, backlog_tree.read(root))


class TheCommandIsNotOnTheLoopsPath(unittest.TestCase):
    def test_only_the_command_line_and_its_own_modules_name_it(self):
        graph = pathlib.Path(__file__).resolve().parents[1]
        its_own = {"remember.py", "remember_events.py", "remember_note.py",
                   "graph-goal.py", "cli_args.py"}
        named = []
        for path in sorted(graph.rglob("*.py")) + sorted(graph.rglob("*.sh")):
            if (path.name in its_own or path.parent.name == "tests"
                    or "__pycache__" in path.parts):
                continue
            if REACHES.search(path.read_text("utf-8")):
                named.append(path.name)
        self.assertEqual([], named, "a hand-run command must stay off the loop's path")

    def test_the_command_line_knows_it_and_it_takes_no_argument(self):
        """Every subcommand answers "marker", so a command added beside this
        one never has to be named here for this to go on passing."""
        parser = build_parser("a test", collections.defaultdict(lambda: "marker"))
        self.assertEqual("marker", parser.parse_args(["remember"]).run)


class AStrangeLogIsCountedNeverRaised(unittest.TestCase):
    def setUp(self):
        self.root = vault()
        self.counts = remember.write_memory(self.root, strange() + good())

    def test_the_rows_it_could_not_read_are_counted(self):
        """Two that are not mappings, one with no time, one with no kind, and
        two of a kind it knows that name no node it can use."""
        self.assertEqual(6, self.counts["unreadable"])

    def test_the_kinds_it_has_no_section_for_are_counted_apart(self):
        self.assertEqual(2, self.counts["no_section"])
        self.assertEqual(1, self.counts["not_a_card"])

    def test_the_events_it_did_understand_still_reach_the_note(self):
        text = (self.root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8")
        self.assertIn("planned", text)
        self.assertIn("the gate ran, exit 0", text)


class TheDoorWritesNothingButRelatives(unittest.TestCase):
    def test_the_command_adds_no_event_of_its_own_to_the_campaign(self):
        root = vault()
        space = Workspace(tempfile.mkdtemp()).init(goal="a goal", backlog=str(root))
        for row in good():
            space.event(row["kind"], **{k: v for k, v in row.items()
                                        if k not in ("at", "kind")})
        before = (space.root / "events.jsonl").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as said:
            self.assertEqual(0, remember.command_remember(
                argparse.Namespace(workspace=str(space.root))))
        self.assertEqual(before, (space.root / "events.jsonl").read_bytes())
        self.assertIn("memory", said.getvalue())

    def test_a_backlog_that_is_one_file_says_so_and_writes_nothing(self):
        flat = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
        flat.write_text(yaml.safe_dump({"tasks": [{"id": "T1", "goal": "a task"}]}), "utf-8")
        space = Workspace(tempfile.mkdtemp()).init(goal="a goal", backlog=str(flat))
        with contextlib.redirect_stdout(io.StringIO()) as said:
            self.assertEqual(0, remember.command_remember(
                argparse.Namespace(workspace=str(space.root))))
        self.assertIn("molecule", said.getvalue())


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
