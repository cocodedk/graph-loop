"""What counts as inside a task's scope when it may add files beside its own:
the 200-line split's new file, and nothing else."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from worktree_scope import added_beside, changed_outside

EXPECTED_TESTS = 9


class MayAddTest(unittest.TestCase):
    def test_a_new_file_beside_its_own_is_allowed_only_when_the_task_may_add(self):
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "pkg").mkdir()
        (tree / "pkg" / "a.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "pkg" / "a_part.py").write_text("two\n")      # the split's new file, beside its own
        (tree / "elsewhere.py").write_text("three\n")         # never
        self.assertEqual(["elsewhere.py", "pkg/a_part.py"], changed_outside(str(tree), ["pkg/a.py"]))
        self.assertEqual(["elsewhere.py"], changed_outside(str(tree), ["pkg/a.py"], may_add=True))
        # an owned file replaced by a directory of the same name carries nothing in
        (tree / "pkg" / "a.py").unlink()
        (tree / "pkg" / "a.py").mkdir()
        (tree / "pkg" / "a.py" / "inner.py").write_text("four\n")
        outside = changed_outside(str(tree), ["pkg/a.py"], may_add=True)
        self.assertIn("pkg/a.py/inner.py", outside)

    def test_a_not_yet_existing_owned_file_still_admits_new_files_beside_it(self):
        # The card's only owned file does not exist in HEAD yet: its directory
        # must still admit a sibling, or may_add_files means nothing for it.
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "README.md").write_text("root\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "tests").mkdir()
        (tree / "tests" / "test_x.py").write_text("one\n")     # the card's own file, new, not in HEAD
        (tree / "tests" / "helper_x.py").write_text("two\n")   # the 200-line split's new file, beside it
        self.assertEqual([], changed_outside(str(tree), ["tests/test_x.py"], may_add=True))
        self.assertEqual(["tests/helper_x.py"], added_beside(str(tree), ["tests/test_x.py"]))

    def test_an_owned_path_absent_from_head_and_disk_admits_no_sibling(self):
        # The card has not written its own file yet -- absent from HEAD and
        # from disk both -- so nothing confirms a FILE there to be beside.
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "README.md").write_text("root\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "tests").mkdir()
        (tree / "tests" / "helper_x.py").write_text("two\n")  # a helper beside a file never written
        self.assertIn("tests/helper_x.py", changed_outside(str(tree), ["tests/test_x.py"], may_add=True))

    def test_a_task_that_owns_a_directory_gets_no_siblings_outside_it(self):
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "pkg").mkdir(); (tree / "pkg" / "a.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "outside.py").write_text("two\n")             # the repository root is NOT a sibling of pkg
        (tree / "pkg" / "new.py").write_text("three\n")       # inside the owned directory, always fine
        self.assertEqual(["outside.py"], changed_outside(str(tree), ["pkg"], may_add=True))
        # even wiped from disk: a deleted owned directory must not turn the root into a sibling
        shutil.rmtree(tree / "pkg")
        (tree / "root_new.py").write_text("four\n")
        self.assertIn("root_new.py", changed_outside(str(tree), ["pkg"], may_add=True))
        # even replaced: a tracked directory turned into a plain file is still
        # a directory by HEAD, so it still admits no sibling in its parent
        (tree / "pkg").write_text("five\n")
        (tree / "root_new2.py").write_text("six\n")
        self.assertIn("root_new2.py", changed_outside(str(tree), ["pkg"], may_add=True))

    def test_a_directory_name_with_a_space_replaced_by_a_file_admits_no_sibling(self):
        # `ls-tree` without `-z` splits (or quotes) on whitespace: a tracked
        # directory whose name has a space must parse correctly too, or
        # replacing it with a file silently opens the repository root.
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "dir with space").mkdir()
        (tree / "dir with space" / "a.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        shutil.rmtree(tree / "dir with space")
        (tree / "dir with space").write_text("two\n")         # the tracked directory, replaced by a file
        (tree / "root_new.py").write_text("three\n")
        self.assertIn("root_new.py", changed_outside(str(tree), ["dir with space"], may_add=True))

    def test_a_nested_repository_beside_an_owned_file_is_not_a_sibling(self):
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "pkg").mkdir(); (tree / "pkg" / "a.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "pkg" / "inner").mkdir()
        subprocess.run(("git", "init", "-q", "-b", "main"), cwd=tree / "pkg" / "inner", capture_output=True, check=True)
        (tree / "pkg" / "inner" / "x.py").write_text("two\n")
        self.assertEqual(["pkg/inner/"], changed_outside(str(tree), ["pkg/a.py"], may_add=True))

    def test_an_owned_gitlink_admits_no_sibling(self):
        # The owned path is itself a committed nested repository (mode
        # 160000): `ls-tree -r` lists it by its own path same as a blob, but
        # it is a directory, not a file, so it must not open its parent.
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "pkg").mkdir()
        (tree / "pkg" / "inner").mkdir()
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree / "pkg" / "inner", capture_output=True, check=True)
        (tree / "pkg" / "inner" / "x.py").write_text("one\n")
        subprocess.run(("git", "add", "-A"), cwd=tree / "pkg" / "inner", capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "inner"), cwd=tree / "pkg" / "inner", capture_output=True, check=True)
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)   # stages pkg/inner as a gitlink
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "pkg" / "sibling.py").write_text("two\n")     # a new file beside the owned gitlink
        self.assertIn("pkg/sibling.py", changed_outside(str(tree), ["pkg/inner"], may_add=True))
        # even replaced: a gitlink is a HEAD entry, so disk never gets a say
        shutil.rmtree(tree / "pkg" / "inner")
        (tree / "pkg" / "inner").write_text("three\n")
        self.assertIn("pkg/sibling.py", changed_outside(str(tree), ["pkg/inner"], may_add=True))
        # even unstaged from the index: HEAD still holds the gitlink
        subprocess.run(("git", "rm", "-q", "--cached", "pkg/inner"), cwd=tree, capture_output=True, check=True)
        self.assertIn("pkg/sibling.py", changed_outside(str(tree), ["pkg/inner"], may_add=True))

    def test_a_deletion_beside_an_owned_file_is_out_of_scope(self):
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        (tree / "pkg").mkdir()
        (tree / "pkg" / "owned.py").write_text("one\n")
        (tree / "pkg" / "other.py").write_text("two\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        (tree / "pkg" / "other.py").unlink()                  # a deletion, not a new file
        self.assertEqual(["pkg/other.py"], changed_outside(str(tree), ["pkg/owned.py"], may_add=True))

    def test_a_rename_beside_an_owned_file_is_out_of_scope(self):
        tree = pathlib.Path(tempfile.mkdtemp())
        for args in (("git", "init", "-q", "-b", "main"), ("git", "config", "user.email", "t@e.test"),
                     ("git", "config", "user.name", "t")):
            subprocess.run(args, cwd=tree, capture_output=True, check=True)
        # root-level, not pkg/: a nested rename's compound "old -> new" path
        # always carries the "/" from its own directory into its parent, so it
        # can never match a real sibling directory there. Only a rename of two
        # root-level files collapses to a parent of "." - the same parent a
        # root-level owned file has - which is the case that actually reached
        # the exempted status codes.
        (tree / "owned.py").write_text("one\n")
        (tree / "other.py").write_text("two\n")
        subprocess.run(("git", "add", "-A"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "first"), cwd=tree, capture_output=True, check=True)
        subprocess.run(("git", "mv", "other.py", "moved.py"), cwd=tree, capture_output=True, check=True)
        self.assertEqual(["other.py -> moved.py"], changed_outside(str(tree), ["owned.py"], may_add=True))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
