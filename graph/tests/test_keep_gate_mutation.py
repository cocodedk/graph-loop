"""A gate that edits the candidate checkout is refused: the gates must judge the
commit that will be published, not a tree they wrote themselves.

Red first (review finding 5): the first gate wrote `helper.py` into the checkout
and passed, the second gate passed only because of that file, and the keeper
published a commit that does not carry it — the branch held a tree no gate had
ever seen.
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

EXPECTED_TESTS = 2


class GateMutationTest(unittest.TestCase):
    def test_a_gate_that_writes_into_the_candidate_tree_is_not_a_pass(self):
        root = repo()
        keeper = Keeper(root, "campaign/test")
        tree = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", tree,
                        keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(tree) / "a.py").write_text("one changed\n")
        before = subprocess.run(("git", "-C", root, "rev-parse", "-q", "--verify",
                                 "campaign/test"), capture_output=True, text=True,
                                check=False).stdout.strip()
        with self.assertRaises(RuntimeError) as caught:
            # The second gate passes only because the first one wrote the file;
            # the commit the keeper would publish does not carry it.
            keeper.keep("T1", tree, "first", files=["a.py"],
                        gates=["echo helper > helper.py", "test -f helper.py"])
        self.assertIn("helper.py", str(caught.exception))       # it says what changed
        self.assertIn("echo helper", str(caught.exception))     # and which gate did it
        after = subprocess.run(("git", "-C", root, "rev-parse", "-q", "--verify",
                                "campaign/test"), capture_output=True, text=True,
                               check=False).stdout.strip()
        self.assertEqual(before, after)                         # the branch did not move

    def test_a_gate_that_rewrites_a_provisioned_file_is_not_a_pass(self):
        # Codex, reviewing the check above: comparing names alone missed an edit
        # to a file already dirty when the gates started. `simulation/secrets` is
        # copied in by `provision` and is untracked, so `?? …/fixture.txt` reads
        # the same before and after a gate overwrites it — and the next gate ran
        # on the edit.
        root = repo()
        (pathlib.Path(root) / "simulation" / "secrets").mkdir(parents=True)
        (pathlib.Path(root) / "simulation" / "secrets" / "fixture.txt").write_text("minted\n")
        keeper = Keeper(root, "campaign/test")
        tree = str(pathlib.Path(tempfile.mkdtemp()) / "T2")
        subprocess.run(("git", "-C", root, "worktree", "add", "-q", "--detach", tree,
                        keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(tree) / "a.py").write_text("two\n")
        with self.assertRaises(RuntimeError) as caught:
            keeper.keep("T2", tree, "second", files=["a.py"],
                        gates=["echo tampered > simulation/secrets/fixture.txt",
                               "grep -q tampered simulation/secrets/fixture.txt"])
        self.assertIn("fixture.txt", str(caught.exception))
        self.assertIn("echo tampered", str(caught.exception))
        self.assertEqual("", subprocess.run(                     # the branch was never made
            ("git", "-C", root, "rev-parse", "-q", "--verify", "campaign/test"),
            capture_output=True, text=True, check=False).stdout.strip())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
