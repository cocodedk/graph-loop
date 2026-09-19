"""A card that uses a name nothing has made is refused before a builder starts.

T26.facts-spec was refused fourteen times and then rejected for naming a
durable field — `outcome_facts` — that no producer emits. Every one of those
refusals cost a model call. This check costs a file read.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import molecule
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 9


def repo(**files) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp())
    for name, body in files.items():
        (root / name).write_text(body, "utf-8")
    return root


class BeforeABuilderIsPaid(unittest.TestCase):
    def setUp(self):
        self.root = repo(app_py='story = {"items": items}')
        self.reader = {"id": "T26.reader", "needs": ["T26.producer"],
                       "uses": ["app_py:outcome_facts"]}
        self.producer = {"id": "T26.producer", "needs": []}

    def test_a_name_nothing_makes_refuses_the_card_and_names_it(self):
        why = molecule.unknown_names(self.reader, [self.producer, self.reader], self.root)
        self.assertIn("app_py:outcome_facts", why)

    def test_the_card_it_waits_for_can_make_the_name(self):
        self.producer["creates"] = ["app_py:outcome_facts"]
        self.assertEqual(
            molecule.unknown_names(self.reader, [self.producer, self.reader], self.root), "")

    def test_a_card_it_does_not_wait_for_cannot(self):
        self.producer["creates"] = ["app_py:outcome_facts"]
        self.reader["needs"] = []
        self.assertNotEqual(
            molecule.unknown_names(self.reader, [self.producer, self.reader], self.root), "")

    def test_a_name_that_is_there_passes(self):
        self.reader["uses"] = ["app_py:items"]
        self.assertEqual(
            molecule.unknown_names(self.reader, [self.producer, self.reader], self.root), "")

    def test_a_card_that_uses_nothing_is_not_this_check_s_business(self):
        self.assertEqual(molecule.unknown_names({"id": "T25"}, [], self.root), "")


class TheLoopRefusesItBeforeAnyoneIsPaid(unittest.TestCase):
    """The check as the loop runs it, not the helper on its own."""

    def loop(self, **extra):
        self.fakes = Fakes()
        return loop_for(task(**extra), self.fakes)

    def test_a_card_naming_what_nothing_makes_never_reaches_a_builder(self):
        loop, book, space = self.loop(uses=["a.py:outcome_facts"])
        out = loop.run_task(book.task("T1"))
        self.assertEqual("refused", out.state)
        self.assertEqual([], self.fakes.calls)
        self.assertEqual("refused_contract", book.task("T1")["status"])
        self.assertTrue(any(row.get("step") == "names" for row in space.events()))

    def test_the_refusal_names_what_is_missing(self):
        loop, book, _ = self.loop(uses=["a.py:outcome_facts"])
        self.assertIn("a.py:outcome_facts", loop.run_task(book.task("T1")).why)

    def test_a_card_naming_what_is_there_is_built(self):
        loop, book, _ = self.loop(uses=["a.py:one"])
        self.assertEqual("done", loop.run_task(book.task("T1")).state)

    def test_a_card_written_wrong_is_refused_and_not_a_crashed_lane(self):
        loop, book, _ = self.loop(uses=["outcome_facts"])   # no path
        out = loop.run_task(book.task("T1"))
        self.assertEqual("refused", out.state)
        self.assertIn("path:text", out.why)
        self.assertEqual([], self.fakes.calls)


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
