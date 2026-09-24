"""Approved sources stay inside the repository, whatever shape the path takes."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import graph_commands

EXPECTED_TESTS = 3


class Space:
    def __init__(self):
        self.events = []

    def event(self, kind, **body):
        self.events.append(dict(body, kind=kind))


class SourceEscapeTest(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        (self.repo / "spec").mkdir()
        (self.repo / "spec" / "a.md").write_text("x")
        self.outside = pathlib.Path(tempfile.mkdtemp())
        (self.outside / "b.md").write_text("y")
        patch = unittest.mock.patch.object(graph_commands.where, "repo", return_value=self.repo)
        patch.start(); self.addCleanup(patch.stop)

    def test_a_dotdot_path_is_refused(self):
        with self.assertRaises(SystemExit):
            graph_commands.declare_sources(Space(), [f"../{self.outside.name}/b.md"])

    def test_a_symlink_out_of_the_repo_is_refused(self):
        (self.repo / "sneaky").symlink_to(self.outside)
        with self.assertRaises(SystemExit):
            graph_commands.declare_sources(Space(), ["sneaky/b.md"])

    def test_a_good_path_is_stored_normalized_and_recorded(self):
        space = Space()
        good = graph_commands.declare_sources(space, ["spec/../spec/a.md"])
        self.assertEqual(["spec/a.md"], good)
        self.assertEqual([{"kind": "sources_declared", "sources": ["spec/a.md"]}],
                         space.events)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
