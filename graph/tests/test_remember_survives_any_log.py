"""Nothing in a campaign's log can stop the export — including its own bytes.

The guard used to sit on projection only, so the log was still read through
`Workspace.events`, which parses every line of every part and raises on the
first one a crash mangled. A `null` line, a truncated object, an init with no
backlog, a lone surrogate that cannot be encoded again: each took the whole
command down with a traceback, on a log the campaign itself survived.

So ingestion is guarded line by line, part by part, rotated parts included. A
line that is not a JSON object is counted and stepped over. The backlog is the
first init event that actually names one. No usable init at all is an answer,
printed, not a traceback.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import cardfile
import remember
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 5

BENT = [
    "null",
    "[1, 2, 3]",
    '"a string on its own"',
    '{"at": "2026-09-20T07:00:00Z", "kind": "attempt", "task": "T30.schema",',
    "not json at all",
    '{"at": "2026-09-20T07:00:01Z", "kind": "init"}',
    '{"at": "2026-09-20T07:00:02Z", "kind": "init", "backlog": null}',
    ('{"at": "2026-09-20T07:00:03Z", "kind": "attempt", "task": "T30.schema", '
     '"account": "\\ud800", "outcome": "ok", "counted": true}'),
]


def vault() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / "vault"
    piece = root / "T30"
    piece.mkdir(parents=True)
    (piece / cardfile.HEAD).write_text(
        cardfile.dump({"goal": "a piece", "status": "sliced"}), "utf-8")
    (piece / "01-schema.md").write_text(
        cardfile.dump({"goal": "the field exists", "status": "todo"}), "utf-8")
    return root


def campaign(root: pathlib.Path, parts: dict) -> pathlib.Path:
    """A campaign directory holding these log parts, written as they stand."""
    space = pathlib.Path(tempfile.mkdtemp()) / "campaign"
    space.mkdir(parents=True)
    for name, lines in parts.items():
        (space / name).write_text("".join(line + "\n" for line in lines), "utf-8")
    return space


def good(root: pathlib.Path) -> list[str]:
    return [json.dumps({"at": "2026-09-20T06:57:49Z", "kind": "init", "goal": "a goal",
                        "backlog": str(root), "branch": "b"}),
            json.dumps({"at": "2026-09-20T06:58:20Z", "kind": "planned", "task": "the plan",
                        "added": ["T30", "T30.schema"]}),
            json.dumps({"at": "2026-09-20T07:05:30Z", "kind": "step", "task": "T30.schema",
                        "step": "gate", "seconds": 8.25, "passed": True, "code": 0})]


def run(space: pathlib.Path) -> tuple[int, str]:
    with contextlib.redirect_stdout(io.StringIO()) as said:
        code = remember.command_remember(argparse.Namespace(workspace=str(space)))
    return code, said.getvalue()


class ABentLineCostsOnlyItself(unittest.TestCase):
    def test_every_bent_line_in_the_open_part_is_counted_and_stepped_over(self):
        root = vault()
        space = campaign(root, {"events.jsonl": BENT + good(root)})
        code, said = run(space)
        self.assertEqual(0, code)
        self.assertIn("the gate ran, exit 0",
                      (root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8"))
        self.assertIn("could not be read", said)

    def test_a_rotated_part_is_read_the_same_way(self):
        root = vault()
        space = campaign(root, {"events-0001.jsonl": BENT + good(root)[:1],
                                "events.jsonl": good(root)[1:] + BENT})
        self.assertEqual(0, run(space)[0])
        self.assertIn("the gate ran, exit 0",
                      (root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8"))

    def test_an_init_that_names_no_backlog_is_stepped_over_for_one_that_does(self):
        root = vault()
        space = campaign(root, {"events.jsonl": [
            '{"at": "2026-09-20T06:00:00Z", "kind": "init"}',
            '{"at": "2026-09-20T06:00:01Z", "kind": "init", "backlog": 41}', *good(root)]})
        self.assertEqual(0, run(space)[0])
        self.assertTrue((root / "T30" / "relatives" / "memory-molecule.md").exists())

    def test_a_lone_surrogate_in_an_event_does_not_stop_the_export(self):
        root = vault()
        space = campaign(root, {"events.jsonl": good(root) + [BENT[-1]]})
        self.assertEqual(0, run(space)[0])
        self.assertIn("the gate ran, exit 0",
                      (root / "T30" / "relatives" / "memory-01-schema.md").read_text("utf-8"))


class ALogWithNoUsableInitIsAnAnswerNotACrash(unittest.TestCase):
    def test_it_says_so_and_returns_rather_than_raising(self):
        space = campaign(vault(), {"events.jsonl": BENT})
        code, said = run(space)
        self.assertEqual(1, code)
        self.assertIn("init", said)


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
