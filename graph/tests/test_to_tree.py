"""The converter's fidelity check: a parent is exempt ONLY in its derived needs."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
_spec = importlib.util.spec_from_file_location(
    "to_tree", pathlib.Path(__file__).resolve().parents[1] / "to-tree.py")
assert _spec is not None and _spec.loader is not None
to_tree = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(to_tree)

EXPECTED_TESTS = 4

ROWS = [
    {"id": "T1", "goal": "parent goal", "status": "todo", "files": ["a.py"],
     "needs": ["EXT"]},
    {"id": "T1.a", "goal": "child", "status": "todo", "files": ["a.py"], "needs": []},
]


class DiffersTest(unittest.TestCase):
    def test_a_parents_drifted_goal_is_still_drift(self):
        seen = [dict(ROWS[0], goal="rewritten goal", needs=["EXT", "T1.a"]), dict(ROWS[1])]
        self.assertEqual({"T1"}, to_tree.differs(ROWS, seen))

    def test_a_parents_derived_needs_are_not_drift(self):
        seen = [dict(ROWS[0], needs=["EXT", "T1.a"]), dict(ROWS[1])]
        self.assertEqual(set(), to_tree.differs(ROWS, seen))

    def test_a_parents_external_need_replaced_is_drift(self):
        seen = [dict(ROWS[0], needs=["WRONG", "T1.a"]), dict(ROWS[1])]
        self.assertEqual({"T1"}, to_tree.differs(ROWS, seen))

    def test_an_atoms_extra_needs_are_drift(self):
        seen = [dict(ROWS[0], needs=["EXT", "T1.a"]), dict(ROWS[1], needs=["T9"])]
        self.assertEqual({"T1.a"}, to_tree.differs(ROWS, seen))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
