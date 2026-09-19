"""`status`'s spend line, tested where the finding named it: unknown review
costs must never be folded into the total as a silent zero (independent
review, drive_commands.py:139, 2026-09-02)."""

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

import drive_commands
from workspace import Workspace

EXPECTED_TESTS = 1


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

    def test_status_shows_known_spend_and_the_unpriced_review_count(self):
        space = _campaign()
        args = types.SimpleNamespace(workspace=str(space.root))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            drive_commands.command_status(args)
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
