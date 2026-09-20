"""TRIAGE's paid-call marker is on the platter before the call it pays for.

One unknown ending buys one belt call per task, and `triage_model` is the record
that says the task has had its one. Appended like any other event, that record
could still be in the page cache when the call returned, so a crash bought the
same classification again (astra's round-3 finding 14).

`watching` and `at` come from test_durable_order.py, the front door of this rig.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from test_durable_order import at, watching

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
from backlog import Backlog
from triage import triage_pending
from triage_signatures import Decision
from workspace import Workspace

EXPECTED_TESTS = 2


class MarkerTest(unittest.TestCase):
    def test_the_marker_is_on_the_platter_before_the_belt_is_asked(self):
        root = pathlib.Path(tempfile.mkdtemp())
        path = root / "backlog.yaml"
        path.write_text(yaml.safe_dump({"tasks": [
            {"id": "T1", "status": "todo", "files": ["a.py"], "gate": "false"},
            {"id": "T2", "status": "todo", "files": ["b.py"], "gate": "false"}]}), "utf-8")
        book, space = Backlog(path), Workspace(root / "campaign")
        space.event("claimed", task="T2")
        space.event("accepted", task="T2")
        space.event("released", task="T2")
        triage_pending(book, space)              # the first catch-up spends nothing
        space.event("claimed", task="T1")
        space.artifact("T1", "gate-output", "one clear assertion failed")
        space.event("failed", task="T1", step="gate")
        space.event("released", task="T1")
        order: list = []

        def asked(*_args, **_kw):
            order.append(("belt call", ""))
            return Decision("rig", "model", "the fixture is wrong")

        with watching(order), mock.patch("triage.decide_unknown", asked):
            triage_pending(book, space, call=object())
        marker = at(self, order, "events.jsonl", '"kind": "triage_model"')
        self.assertLess(marker, at(self, order, "belt call"),
                        "the call was bought before the record that says it was")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
