"""A published child's files are on the platter before its parent settles.

The slicer wrote the molecule's files with a plain rename and then settled the
parent through `durable.replace`, so power loss could keep a parent marked
`sliced` and lose the child that carries its work — planning nobody paid for
twice (astra's round-3 finding 14). The parent's own write was already durable;
now the child's files go down first.

`watching` and `at` come from test_durable_order.py, the front door of this rig:
one fake `os.fsync` records what reached the platter, in order, with the content
of each file, because parent and child are both called molecule.md.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_durable_order import at, watching

HERE = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(HERE / "slicer"))
from backlog import Backlog
from tree import publish  # type: ignore[import-not-found]

EXPECTED_TESTS = 2


def molecule(name: str) -> dict:
    return {"name": name, "source": ["specs/example.md:1"], "goal": f"build {name}",
            "why": "it is absent", "needs": [], "atoms": [],
            "files": [f"{name}.py"], "gate": "false", "done_when": f"{name} works"}


class ChildBeforeParentTest(unittest.TestCase):
    def test_the_childs_files_are_on_the_platter_before_the_parent_is_sliced(self):
        root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        root.mkdir()
        book = Backlog(root)
        publish(root, molecule("large"))
        book.set_status("large", "needs_slice", refused_why="too broad")
        order: list = []
        with watching(order):
            publish(root, molecule("small"), "large")
        self.assertEqual("sliced", book.task("large")["status"])
        child = at(self, order, "molecule.md", "sliced_from: large")
        named = at(self, order, f"{root.name}/")
        parent = at(self, order, "molecule.md", "status: sliced")
        self.assertLess(child, parent,
                        "the parent settled before the child it names was on the platter")
        # and the rename that gave the folder its name: the files inside it are
        # no use if the entry naming them is still in the page cache
        self.assertLess(named, parent,
                        "the parent settled before the child's own name was on the platter")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
