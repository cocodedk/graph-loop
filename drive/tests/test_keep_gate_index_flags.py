"""A gate cannot hide an edit behind git's own index flags, and it cannot move
the repository's main line.

Red first (round-2 finding 3): the candidate checkout's state was read from what
`git status` calls dirty, so a gate that ran `update-index --assume-unchanged` on
a tracked file and then rewrote it left the fingerprint identical. The next gate
read the edit and passed on it, and the keeper published a commit that never held
it.

Red again (astra round 3, finding 1): the candidate checkout was a LINKED
worktree, so it shared the repository's refs — a gate that moved
`refs/heads/main` moved the real `main`, and this file asserted that corruption.
The checkout is a private clone now.

Red a third time (Codex, on that clone): the clone stops the ref writes git
makes from INSIDE the checkout and nothing else — a gate line naming the
repository's own `--git-dir` reaches straight past it, and with the gate box
unavailable (the documented fallback, and this machine) that write lands on the
real `main` and the keep published. So the repository's own protected refs are
read before and after every gate too, with their symbolic targets.

The five cases come in two families. The first three go through `_keep`, which
reads every protected branch before and after and asserts they all stand where
they stood: git inside the checkout cannot reach them. The last two go through
`_refused` and move a repository ref on purpose — one writing it, one turning it
into an alias for another branch at the same commit — because a write that names
the repository's `--git-dir` cannot be prevented from here, only refused. Each
of those two proves the corruption really happened and that the keep was refused
for it.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import gate_sandbox
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep import Keeper
from keep_branch import protected
from test_keep import repo

EXPECTED_TESTS = 5


class IndexFlagTest(unittest.TestCase):
    def setUp(self):
        self.root = repo()
        self.keeper = Keeper(self.root, "campaign/test")
        self.tree = str(pathlib.Path(tempfile.mkdtemp()) / "T1")
        subprocess.run(("git", "-C", self.root, "worktree", "add", "-q", "--detach",
                        self.tree, self.keeper.tip()), capture_output=True, check=True)
        (pathlib.Path(self.tree) / "b.py").write_text("this card's own work\n")

    def _read(self, name: str) -> str:
        # `-q --verify`, not `test_keep.sha`: a protected name the fixture does
        # not have (`master`) is "" here, not an exception.
        return subprocess.run(("git", "-C", self.root, "rev-parse", "-q", "--verify", name),
                              capture_output=True, text=True, check=False).stdout.strip()

    def _refused(self, *gates: str) -> str:
        """The refusal these gates raise; the branch is never made."""
        with self.assertRaises(RuntimeError) as caught:
            self.keeper.keep("T1", self.tree, "the card's work", files=["b.py"],
                             gates=list(gates))
        self.assertEqual("", self._read("campaign/test"))   # the branch was never made
        return str(caught.exception)

    def _keep(self, *gates: str) -> str:
        before = {name: self._read(name) for name in protected(self.root)}
        said = self._refused(*gates)
        # And the repository's own branches stand where they stood: the gates run
        # in a checkout whose refs are its own, so ordinary git inside it never
        # reaches these. The two `--git-dir` cases at the end of this class do
        # reach them, and go through `_refused` for that reason.
        self.assertEqual(before, {name: self._read(name) for name in protected(self.root)})
        return said

    def test_a_gate_that_marks_a_file_assume_unchanged_is_not_a_pass(self):
        # The second gate passes only because the first rewrote `a.py`; the
        # commit the keeper would publish still holds the old one.
        said = self._keep("git update-index --assume-unchanged a.py && echo helper > a.py",
                          "grep -q helper a.py")
        self.assertIn("a.py", said)
        self.assertIn("assume-unchanged", said)   # and which gate did it

    def test_a_gate_that_moves_the_main_line_is_not_a_pass(self):
        """Inside the clone the ref hook refuses the write, so the gate is red
        and the keep is refused; `_keep`'s sweep is what proves the repository's
        own `main` never moved."""
        said = self._keep("git update-ref refs/heads/main HEAD")
        self.assertIn("main", said)                        # and which gate tried it

    def test_a_gate_that_moves_a_default_branch_of_another_name_is_not_a_pass(self):
        # Codex, on the first version of this check: `main` and `master` were
        # read by name, so a repository whose declared default is `trunk` —
        # protected by `checked_destination`, which resolves it from
        # `origin/HEAD` — was fingerprinted by neither, and the keep published.
        # The clone has no remote, so those names are resolved in the REPOSITORY
        # and passed in (`keep_gate._main_line`).
        for args in (("branch", "trunk"),
                     ("update-ref", "refs/remotes/origin/trunk", "HEAD"),
                     ("symbolic-ref", "refs/remotes/origin/HEAD",
                      "refs/remotes/origin/trunk")):
            subprocess.run(("git", "-C", self.root, *args), capture_output=True, check=True)
        said = self._keep("git update-ref refs/heads/trunk HEAD")
        self.assertIn("trunk", said)

    def test_a_gate_that_names_the_repositorys_git_dir_is_not_a_pass(self):
        """The clone holds its own refs, so git inside the checkout cannot reach
        the repository's — but a gate line that names `--git-dir` writes to them
        directly (Codex, on the first version of this isolation). Detected, not
        prevented: the repository's protected refs are read before and after
        every gate, and any change refuses the keep."""
        # The gate box would refuse the write, but it is unavailable on plenty of
        # hosts and the loop says so and runs the gate anyway; the fallback is
        # pinned here so the guard is proved where it is actually needed.
        was = self._read("main")
        with unittest.mock.patch.object(gate_sandbox, "works", lambda: False):
            said = self._refused(f"git --git-dir={self.root}/.git update-ref "
                                 "refs/heads/main $(git rev-parse HEAD)")
        # The refusal names the ref AND where it was read: the gate's own text
        # holds "refs/heads/main" too, and that would pass for any red gate.
        self.assertIn("refs/heads/main (the repository's own)", said)
        self.assertNotEqual(was, self._read("main"))        # it really did reach past the clone

    def test_a_gate_that_makes_the_main_line_a_symbolic_ref_is_not_a_pass(self):
        """`main` pointing AT another branch at the same commit: the sha reads
        identical, so the fingerprint saw nothing and the keep published (Codex,
        on the repository read) — and from then on whatever moves that branch
        moves the main line. The symbolic target is part of the reading now."""
        subprocess.run(("git", "-C", self.root, "branch", "other"),
                       capture_output=True, check=True)   # the alias's target, same commit
        with unittest.mock.patch.object(gate_sandbox, "works", lambda: False):
            said = self._refused(f"git --git-dir={self.root}/.git symbolic-ref "
                                 "refs/heads/main refs/heads/other")
        self.assertIn("refs/heads/main (the repository's own)", said)
        self.assertEqual("refs/heads/other", subprocess.run(   # it really did make it an alias
            ("git", "-C", self.root, "symbolic-ref", "-q", "refs/heads/main"),
            capture_output=True, text=True, check=False).stdout.strip())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
