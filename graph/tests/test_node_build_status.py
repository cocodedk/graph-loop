"""A turn derives each named node's build status from its cards."""

import pathlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import tmp_root  # noqa: F401 — keep temporary test files under the shared root

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import cardfile
from driver_turn import rollup_nodes


class NodeBuildStatusTest(unittest.TestCase):
    def test_rollup_groups_sources_and_preserves_the_note(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            node = root / "node.md"
            other = root / "other.md"
            original = "---\ntitle: Keep this # comment\nbuild_status: pending\n---\nProse.\n"
            node.write_text(original)
            other.write_text("Plain prose.\n")
            rows = [
                {"id": "a", "status": "done", "source": ["node.md:1", "other.md:2"]},
                {"id": "b", "status": "todo", "source": "node.md:9"},
                {"id": "c", "status": "done"},
            ]
            book = Mock()
            book.tasks.return_value = rows
            with patch("driver_turn.where.repo", return_value=root):
                rollup_nodes(book, Mock())
                self.assertEqual(node.read_text(), original)
                self.assertEqual(other.read_text(), "---\nbuild_status: done\n---\nPlain prose.\n")
                rows[1]["status"] = "done"
                rollup_nodes(book, Mock())
                self.assertEqual(node.read_text(), original.replace("pending", "done"))
                rows[1]["status"] = "quarantined"
                rollup_nodes(book, Mock())
                self.assertEqual(cardfile.load(node)["build_status"], "pending")

    def test_sliced_parent_waits_for_its_children_and_dropped_is_finished(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            node = root / "node.md"
            node.write_text("---\nbuild_status: done\n---\n")
            rows = [
                {"id": "parent", "status": "sliced", "source": ["node.md:1"]},
                {"id": "child", "status": "todo", "sliced_from": "parent"},
                {"id": "discarded", "status": "dropped", "source": ["node.md:2"]},
            ]
            book = Mock()
            book.tasks.return_value = rows
            with patch("driver_turn.where.repo", return_value=root):
                rollup_nodes(book, Mock())
                self.assertEqual(cardfile.load(node)["build_status"], "pending")
                rows[1]["status"] = "done"
                rollup_nodes(book, Mock())
                self.assertEqual(cardfile.load(node)["build_status"], "done")
