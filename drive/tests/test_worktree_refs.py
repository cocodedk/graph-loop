"""Every ref write a builder can attempt from inside its own checkout —
switching to a brand-new branch, creating one without switching, resetting to
a commit that never grew there, and a switch to a branch that already exists
— is either refused by `lib/hooks/reference-transaction` or caught by
`Worktree.on_base` checking HEAD. What neither of those sees at all — a
rewrite of a shared branch ref by any spelling — is `test_worktree_private_
refs`'s, the same 200-line split, same as the sneaky-commit case is
`test_loop_uncommit`'s.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from loop import Loop
from providers import Outcome
from test_loop import Fakes, loop_for, repo_with, task

EXPECTED_TESTS = 5


def git(root, *args) -> str:
    """A single-value git lookup, stripped. A ref check that may go either way
    stays a raw, unchecked `subprocess.run` instead."""
    return subprocess.run(("git", "-C", root, *args), capture_output=True,
                          text=True, check=True).stdout.strip()


class NewBranchRefusedTest(unittest.TestCase):
    def test_switching_to_a_new_branch_inside_the_worktree_is_refused(self):
        fakes = Fakes()
        returncode = None
        stderr = ""

        def switches(prompt, *, account, cwd, files, tools, denies, guard, effort="",
                     resume="", model=""):
            nonlocal returncode, stderr
            fakes.calls.append(f"build:{account}")
            done = subprocess.run(("git", "-C", cwd, "switch", "-q", "-c", "campaign/test"),
                                  capture_output=True, text=True, check=False)
            returncode, stderr = done.returncode, done.stderr
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            return Outcome("ok", text="done")

        root, book, space = repo_with(task())
        base = git(root, "rev-parse", "HEAD")
        loop = Loop(repo=root, backlog=book, space=space, build=switches,
                   review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))
        self.assertNotEqual(0, returncode)
        self.assertIn("aborted by hook", stderr)
        self.assertEqual("done", out.state, out.why)
        self.assertEqual("1", git(root, "rev-list", "--count", f"{base}..campaign/test"))


class StrayBranchRefusedTest(unittest.TestCase):
    def test_a_branch_created_without_switching_is_refused_and_never_exists(self):
        fakes = Fakes()
        returncode = None
        stderr = ""

        def branches(prompt, *, account, cwd, files, tools, denies, guard, effort="",
                     resume="", model=""):
            nonlocal returncode, stderr
            fakes.calls.append(f"build:{account}")
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            subprocess.run(("git", "-C", cwd, "add", "-A"), check=True, capture_output=True)
            done = subprocess.run(("git", "-C", cwd, "branch", "scratch", "HEAD"),
                                  capture_output=True, text=True, check=False)
            returncode, stderr = done.returncode, done.stderr
            return Outcome("ok", text="done")

        loop, book, _ = loop_for(task(), fakes)
        loop.build = branches
        out = loop.run_task(book.task("T1"))
        self.assertNotEqual(0, returncode)
        self.assertIn("aborted by hook", stderr)
        self.assertEqual("done", out.state, out.why)
        exists = subprocess.run(("git", "-C", loop.repo, "rev-parse", "--verify", "--quiet",
                                 "refs/heads/scratch"), capture_output=True, check=False)
        self.assertNotEqual(0, exists.returncode)   # never created


class ForeignResetRefusedTest(unittest.TestCase):
    def test_a_reset_to_a_foreign_commit_moves_nothing_the_hook_covers(self):
        # `reset --hard` changes the index and working tree BEFORE it tries to
        # move HEAD, so a refusal here still leaves the ref safe — but
        # observed, not assumed: the working tree already holds the foreign
        # commit's own content the instant the command returns.
        fakes = Fakes()
        returncode = None
        stderr = ""
        seen_head = seen_status = seen_content = ""

        def resets(prompt, *, account, cwd, files, tools, denies, guard, effort="",
                  resume="", model=""):
            nonlocal returncode, stderr, seen_head, seen_status, seen_content
            fakes.calls.append(f"build:{account}")
            done = subprocess.run(("git", "-C", cwd, "reset", "--hard", foreign),
                                  capture_output=True, text=True, check=False)
            returncode, stderr = done.returncode, done.stderr
            seen_head = git(cwd, "rev-parse", "HEAD")
            seen_status = subprocess.run(("git", "-C", cwd, "status", "--short"),
                                         capture_output=True, text=True, check=True).stdout
            seen_content = (pathlib.Path(cwd) / "a.py").read_text()
            (pathlib.Path(cwd) / "a.py").write_text("two\n")   # the builder's own, real edit
            return Outcome("ok", text="done")

        root, book, space = repo_with(task())
        base = git(root, "rev-parse", "HEAD")
        # `repo_with` also commits backlog.yaml: keep every base entry (do not
        # assume a.py is alone) and replace only a.py's own blob.
        base_tree = git(root, "rev-parse", f"{base}^{{tree}}")
        listing = "\n".join(line for line in git(root, "ls-tree", base_tree).splitlines()
                            if not line.endswith("\ta.py")) + "\n"
        blob = subprocess.run(("git", "-C", root, "hash-object", "-w", "--stdin"),
                              input="foreign\n", capture_output=True, text=True,
                              check=True).stdout.strip()
        foreign_tree = subprocess.run(("git", "-C", root, "mktree"),
                                      input=listing + f"100644 blob {blob}\ta.py\n",
                                      capture_output=True, text=True, check=True).stdout.strip()
        foreign = git(root, "commit-tree", foreign_tree, "-p", base, "-m", "a foreign commit")

        loop = Loop(repo=root, backlog=book, space=space, build=resets,
                   review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))
        self.assertNotEqual(0, returncode)
        self.assertIn("aborted by hook", stderr)
        self.assertEqual(base, seen_head)             # the ref never moved
        self.assertEqual("M  a.py\n", seen_status)     # ...but the working tree already had
        self.assertEqual("foreign\n", seen_content)    # ...the foreign commit's own content
        self.assertEqual("done", out.state, out.why)   # the builder's own edit still lands


class ExistingBranchSwitchCaughtTest(unittest.TestCase):
    def test_switching_to_an_existing_branch_off_base_is_caught_and_discarded(self):
        # `git switch <existing branch>` moves HEAD by a symbolic-ref update,
        # which the hook does not cover — not refused. `Worktree.on_base` is
        # the one thing that catches it. A checkout is a private clone, so the
        # only branch it holds locally without first CREATING one (itself a
        # refused write) is the repo's default, `main`; a task with earlier
        # work on campaign/test is based off THAT, so switching to `main` is "off base".
        fakes = Fakes()
        returncode = None
        cwd_seen = ""

        root, book, space = repo_with(task())
        base = git(root, "rev-parse", "HEAD")
        base_tree = git(root, "rev-parse", f"{base}^{{tree}}")
        # An earlier task's work, already on the campaign branch — a distinct
        # sha `main` never points to, and this round's own base.
        ahead = git(root, "commit-tree", base_tree, "-p", base, "-m", "earlier work")
        subprocess.run(("git", "-C", root, "update-ref", "refs/heads/campaign/test", ahead),
                       check=True, capture_output=True)

        def switches(prompt, *, account, cwd, files, tools, denies, guard, effort="",
                     resume="", model=""):
            nonlocal returncode, cwd_seen
            fakes.calls.append(f"build:{account}")
            cwd_seen = cwd
            done = subprocess.run(("git", "-C", cwd, "switch", "main"),
                                  capture_output=True, text=True, check=False)
            returncode = done.returncode
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            return Outcome("ok", text="done")

        loop = Loop(repo=root, backlog=book, space=space, build=switches,
                   review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))

        self.assertEqual(0, returncode)                     # the switch is not refused
        self.assertEqual("harness", out.state, out.why)
        self.assertFalse(pathlib.Path(cwd_seen).exists())    # the tree is discarded
        self.assertEqual(ahead, git(root, "rev-parse", "campaign/test"))   # no new commit landed

        row = book.task("T1")
        self.assertEqual("todo", row["status"])
        self.assertEqual(1, row.get("rebuild_round"))
        self.assertNotIn("rebuild_from", row)
        self.assertNotIn("refused_why", row)
        expected_note = (f"Your previous call left HEAD on {base}, off the task's "
                         "base. Start the work over from the base in this worktree, "
                         "finish, and say DONE.")
        self.assertEqual([expected_note], row.get("rejections"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
