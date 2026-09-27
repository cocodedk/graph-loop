"""What gets copied into a worktree belongs to the repository, not to the loop.

The loop used to copy four fixed directories of one project into every worktree
it made — a private special case with no way to turn it off. `provision` reads
what to carry from `GRAPH_PROVISION_COPY` and `GRAPH_PROVISION_LINK` now, and a
repository that names neither gets a plain checkout.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from worktree_provision import carried, provision

EXPECTED_TESTS = 7


def trees() -> tuple[pathlib.Path, pathlib.Path]:
    repo, tree = pathlib.Path(tempfile.mkdtemp()), pathlib.Path(tempfile.mkdtemp())
    (repo / "runtime").mkdir()
    (repo / "runtime" / "key.txt").write_text("minted", "utf-8")
    (repo / "interpreter").mkdir()
    return repo, tree


def checkout(tree: pathlib.Path, ignore: str) -> None:
    """A worktree is a git checkout carrying its repository's ignore rules."""
    subprocess.run(["git", "init", "-q", str(tree)], check=True)
    (tree / ".gitignore").write_text(ignore, "utf-8")


class ProvisionTest(unittest.TestCase):
    def test_nothing_named_means_a_plain_checkout(self):
        repo, tree = trees()
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_COPY": "",
                                          "GRAPH_PROVISION_LINK": ""}):
            provision(str(tree), str(repo))
        self.assertEqual([], sorted(p.name for p in tree.iterdir()))

    def test_a_named_folder_is_copied_in(self):
        repo, tree = trees()
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_COPY": "runtime"}):
            provision(str(tree), str(repo))
        self.assertEqual("minted", (tree / "runtime" / "key.txt").read_text("utf-8"))
        self.assertFalse((tree / "runtime").is_symlink(), "copied, never linked")

    def test_a_named_folder_is_linked_not_copied(self):
        repo, tree = trees()
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": "interpreter"}):
            provision(str(tree), str(repo))
        self.assertTrue((tree / "interpreter").is_symlink())

    def test_a_link_git_would_carry_is_named(self):
        # a symlink is a file to git, so a pattern for folders does not ignore it
        repo, tree = trees()
        checkout(tree, "interpreter/\n")
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": "interpreter"}):
            provision(str(tree), str(repo))
            self.assertIn("?? interpreter", carried(str(tree)))

    def test_ignored_contents_of_a_copied_folder_are_not_carried(self):
        repo, tree = trees()
        checkout(tree, "runtime/*\n")
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_COPY": "runtime"}):
            provision(str(tree), str(repo))
            self.assertEqual([], carried(str(tree)))

    def test_a_name_git_would_read_as_magic_is_asked_literally(self):
        # `:cache` is pathspec magic to git; the question is about the path itself
        repo, tree = trees()
        (repo / ":cache").mkdir()
        checkout(tree, "interpreter\n")
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": ":cache"}):
            provision(str(tree), str(repo))
            self.assertIn("?? :cache", carried(str(tree)))

    def test_a_trailing_slash_in_the_setting_names_the_same_path(self):
        repo, tree = trees()
        checkout(tree, "interpreter\n")
        with mock.patch.dict(os.environ, {"GRAPH_PROVISION_LINK": "interpreter/"}):
            provision(str(tree), str(repo))
            self.assertTrue((tree / "interpreter").is_symlink())
            self.assertEqual([], carried(str(tree)))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
