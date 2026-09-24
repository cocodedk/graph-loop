"""A file whose name is not ASCII is in the commit that accepts it.

Red first (round-2 finding 9): the keeper read `diff --cached --name-only` and
split it on newlines, so git handed it `"caf\303\251.py"` — the C-quoted form,
which is not a path. Nothing existed at that name, so the keep force-removed it
from the index and published a commit without the file the card was accepted for.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper
from test_keep import repo

EXPECTED_TESTS = 1


class UnicodeNameTest(unittest.TestCase):
    def test_a_name_git_would_quote_is_kept_under_its_real_name(self):
        root = repo()
        keeper = Keeper(root, "campaign/test")
        tree = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", tree,
                        keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(tree) / "café.py").write_text("naïve\n")
        commit = keeper.keep("T1", tree, "added a file with an accent")
        self.assertTrue(commit)
        # `-z` on the reading side too: the quoting this test exists for would
        # otherwise hide the failure it is looking for.
        listing = subprocess.run(("git", "-C", root, "ls-tree", "-z", "--name-only",
                                  "campaign/test"), capture_output=True, check=True).stdout
        self.assertIn("café.py".encode(), listing)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
