"""A published molecule is ordinary input to the unchanged drive backlog."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

HERE = pathlib.Path(__file__).resolve().parents[1]
DRIVE_LIB = HERE.parent / "drive" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DRIVE_LIB))
from backlog import Backlog  # type: ignore[import-not-found]
from tree import publish

EXPECTED_TESTS = 6


def task(name: str, *, needs=(), atoms=()) -> dict:
    body = {"name": name, "source": ["specs/example.md:1"], "goal": f"build {name}",
            "why": "it is absent", "needs": list(needs), "atoms": list(atoms)}
    if not atoms:
        body.update(files=[f"{name}.py"], gate="false", done_when=f"{name} works")
    return body


def atom(name: str, stage: int) -> dict:
    return {"name": name, "stage": stage, "goal": f"build {name}",
            "files": [f"{name}.py"], "gate": "false", "done_when": f"{name} works"}


class Publishing(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp()) / "backlog"
        self.root.mkdir()
        self.book = Backlog(self.root)

    def test_a_molecule_of_one_is_startable_by_the_unchanged_picker(self):
        publish(self.root, task("greeting"))
        self.assertEqual(["greeting"], [row["id"] for row in self.book.startable()])
        self.assertTrue(self.book.task("greeting")["gate_reviewed_first"])

    def test_file_numbers_are_the_stage_and_equal_stages_stay_parallel(self):
        publish(self.root, task("feature", atoms=[atom("schema", 1), atom("left", 2),
                                                   atom("right", 2)]))
        rows = {row["id"]: row for row in self.book.tasks()}
        self.assertEqual(["feature.schema"], rows["feature.left"]["needs"])
        self.assertEqual(["feature.schema"], rows["feature.right"]["needs"])

    def test_a_child_molecule_settles_the_leaf_it_replaces(self):
        publish(self.root, task("large"))
        publish(self.root, task("after", needs=["large"]))
        self.book.set_status("large", "needs_slice", refused_why="too broad")
        publish(self.root, task("small"), "large")
        self.assertEqual("sliced", self.book.task("large")["status"])
        self.assertNotIn("after", [row["id"] for row in self.book.startable()])
        self.book.set_status("small", "done")
        self.assertIn("after", [row["id"] for row in self.book.startable()])

    def test_recovery_links_one_already_published_child_once(self):
        publish(self.root, task("large"))
        publish(self.root, task("small"), "large")
        publish(self.root, task("small"), "large")
        row = self.book.task("large")
        self.assertEqual(1, row["needs"].count("small"))

    def test_a_settled_parent_cannot_gain_a_second_child(self):
        publish(self.root, task("large"))
        publish(self.root, task("small"), "large")
        with self.assertRaisesRegex(ValueError, "already has"):
            publish(self.root, task("other"), "large")

    def test_a_slice_of_a_slice_releases_the_original_lineage(self):
        publish(self.root, task("large"))
        publish(self.root, task("after", needs=["large"]))
        publish(self.root, task("small"), "large")
        publish(self.root, task("tiny"), "small")
        self.book.set_status("tiny", "done")
        self.assertIn("after", [row["id"] for row in self.book.startable()])


class Count(unittest.TestCase):
    def test_the_file_holds_the_count_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS + 1, found)


if __name__ == "__main__":
    unittest.main()
