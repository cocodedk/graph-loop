"""`status`'s spend line, tested where the finding named it: unknown review
costs must never be folded into the total as a silent zero (independent
review, graph_commands.py:139, 2026-09-02)."""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import types
import unittest

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(HERE))

import graph_commands
from workspace import Workspace

EXPECTED_TESTS = 2


def _campaign() -> Workspace:
    """One paid build attempt, one priced review, one review with no figure."""
    backlog_path = pathlib.Path(tempfile.mkdtemp()) / "b.yaml"
    backlog_path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": []}))
    space = Workspace(tempfile.mkdtemp()).init(goal="g", backlog=str(backlog_path))
    space.attempt("T1", account="work", kind="ok", cost=1.5, tokens=100)
    space.attempt("T1", account="second", kind="ok", cost=0.4, tokens=50, purpose="review")
    space.attempt("T1", account="second", kind="ok", tokens=50, purpose="review")
    return space


class StatusReviewSpendTest(unittest.TestCase):
    """`status` used to sum every attempt's cost itself, folding a review with
    no cost figure in as a silent zero. It must print report(space)'s own
    known/unknown split instead (one home for the numbers: report.py)."""

    def test_status_rolls_up_only_named_nodes_without_writing_notes(self):
        space = _campaign()
        path = pathlib.Path(graph_commands._backlog_of(space))
        rows = [{"id": "T1", "status": "done", "node": "[[N01-read]]"},
                {"id": "T2", "status": "todo", "node": "[[N01-read]]"},
                {"id": "T3", "status": "done", "node": "[[N02-write]]"},
                {"id": "T4", "status": "rejected", "node": "[[N03-check]]"},
                {"id": "T5", "status": "todo"}]
        path.write_text(yaml.safe_dump({"tasks": rows}))
        node = space.root / "N01-read.md"
        node.write_text("A node note stays as written.\n")
        before = {p: p.read_bytes() for p in space.root.rglob("*") if p.is_file()}
        backlog_before = path.read_bytes()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, graph_commands.command_status(
                types.SimpleNamespace(workspace=str(space.root))))
        for line in out.getvalue().splitlines():
            self.assertRegex(line, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ")
        lines = [line.split(" ", 1)[1].strip()
                 for line in out.getvalue().splitlines() if "node [[" in line]
        self.assertEqual(["node [[N01-read]]: 1 done / 1 open",
                          "node [[N02-write]]: 1 done / 0 open — built",
                          "node [[N03-check]]: 0 done / 1 open"], lines)
        self.assertEqual(before, {p: p.read_bytes() for p in space.root.rglob("*") if p.is_file()})
        self.assertEqual(backlog_before, path.read_bytes())

    def test_status_shows_known_spend_and_the_unpriced_review_count(self):
        space = _campaign()
        args = types.SimpleNamespace(workspace=str(space.root))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            graph_commands.command_status(args)
        text = out.getvalue()
        self.assertIn("known spend: $1.90", text)     # 1.50 build + 0.40 review, both known
        self.assertIn("reviews: $0.40 known, 1 calls with no figure", text)
        self.assertNotIn("reported spend", text)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
