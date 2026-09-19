"""CODE builders hold `Bash(git *)`. A builder that commits inside its own
worktree is refused: `lib/hooks/reference-transaction` (installed per
worktree by `Worktree.create`) fails any ref write attempted from inside it,
so the sneaky commit never lands and the campaign branch holds only the
keeper's own. Every other ref mutation a builder can attempt is
`test_worktree_refs`'s, the same 200-line split.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from loop import Loop
from providers import Outcome
from test_loop import Fakes, repo_with, task

EXPECTED_TESTS = 2


class SneakyCommitRefusedTest(unittest.TestCase):
    def test_a_sneaky_commit_inside_the_worktree_is_refused_not_kept(self):
        fakes = Fakes()
        returncode = None
        stderr = ""

        def sneaky(prompt, *, account, cwd, files, tools, denies, guard, effort="",
                   resume="", model=""):
            nonlocal returncode, stderr
            fakes.calls.append(f"build:{account}")
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            subprocess.run(("git", "-C", cwd, "add", "-A"), check=True, capture_output=True)
            done = subprocess.run(("git", "-C", cwd, "-c", "user.email=b@x", "-c", "user.name=b",
                                   "commit", "-qm", "sneaky"), capture_output=True, text=True,
                                  check=False)
            returncode, stderr = done.returncode, done.stderr
            return Outcome("ok", text="done")

        root, book, space = repo_with(task())
        base = subprocess.run(("git", "-C", root, "rev-parse", "HEAD"), capture_output=True,
                              text=True, check=True).stdout.strip()
        loop = Loop(repo=root, backlog=book, space=space, build=sneaky,
                   review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))
        self.assertNotEqual(0, returncode)
        self.assertIn("aborted by hook", stderr)
        self.assertEqual("done", out.state, out.why)
        self.assertTrue(book.task("T1")["commit"])
        head = subprocess.run(("git", "-C", out.worktree, "rev-parse", "HEAD"),
                              capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(base, head)   # HEAD in the worktree never moved
        shown = subprocess.run(("git", "-C", root, "show", "campaign/test:a.py"),
                               capture_output=True, text=True, check=True)
        self.assertEqual("two\n", shown.stdout)
        count = subprocess.run(("git", "-C", root, "rev-list", "--count", f"{base}..campaign/test"),
                               capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual("1", count)   # the keeper's commit alone, not sneaky-plus-keeper


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
