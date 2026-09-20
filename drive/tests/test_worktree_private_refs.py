"""What no hook and no `Worktree.on_base` check ever sees: a rewrite of a
SHARED branch ref, by any spelling, from inside a builder's own checkout.
`symbolic-ref` re-points a ref other than HEAD, which `on_base` (reading only
HEAD) never looks at and which git before 2.55 kept out of the hook; a raw
file write goes through no git code at all. In a linked worktree,
either one reaches the repo directly — `symbolic-ref refs/heads/campaign/
test refs/heads/main` would make the campaign branch literally BE main, and
the keeper's own `update-ref` would then move main itself. A task checkout
is a private clone with its own `.git`: the write lands, but only there, and
is discarded with the checkout. Split from `test_worktree_refs` at the
200-line cap.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from loop import Loop
from providers import Outcome
from test_loop import Fakes, repo_with, task
from test_worktree_refs import REFUSED, git
from worktree import Worktree

EXPECTED_TESTS = 6


class SymbolicRefRewriteTest(unittest.TestCase):
    def test_a_symbolic_ref_rewrite_of_the_campaign_branch_never_moves_main(self):
        fakes = Fakes()
        returncode = None
        stderr = ""

        def rewires(prompt, *, account, cwd, files, tools, denies, guard, effort="",
                    resume="", model=""):
            nonlocal returncode, stderr
            fakes.calls.append(f"build:{account}")
            done = subprocess.run(("git", "-C", cwd, "symbolic-ref",
                                   "refs/heads/campaign/test", "refs/heads/main"),
                                  capture_output=True, text=True, check=False)
            returncode, stderr = done.returncode, done.stderr
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            return Outcome("ok", text="done")

        root, book, space = repo_with(task())
        base = git(root, "rev-parse", "main")
        loop = Loop(repo=root, backlog=book, space=space, build=rewires,
                   review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))
        # Git before 2.55 kept symref updates out of the hook, so this ran;
        # 2.55 refuses it. Whether it runs at all is git's business; the repo
        # being untouched either way is this test's, and the checkout's own
        # `.git` is what makes it so.
        self.assertTrue(returncode == 0 or REFUSED in stderr, stderr)
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(base, git(root, "rev-parse", "main"))          # main never moved
        symbolic = subprocess.run(("git", "-C", root, "symbolic-ref", "-q",
                                   "refs/heads/campaign/test"), capture_output=True, check=False)
        self.assertNotEqual(0, symbolic.returncode)     # a normal ref, not a symlink to main
        self.assertEqual("1", git(root, "rev-list", "--count", f"{base}..campaign/test"))
        shown = subprocess.run(("git", "-C", root, "show", "campaign/test:a.py"),
                               capture_output=True, text=True, check=True)
        self.assertEqual("two\n", shown.stdout)


class DirectRefFileWriteTest(unittest.TestCase):
    def test_a_raw_file_write_to_mains_ref_never_reaches_the_repo(self):
        # "a direct file write skips everything" — not a git command at all, so
        # only a `.git` of its own, not a hook, can make this land nowhere.
        # `--git-path` finds the real file the way a shell-holding builder would
        # rather than guessing `.git/refs/...`: it resolves to the checkout's OWN
        # `.git` for a private clone, and to the shared repo's for a linked one.
        fakes = Fakes()

        root, book, space = repo_with(task())
        base = git(root, "rev-parse", "main")
        # A valid, foreign commit — not garbage bytes — so a shared object
        # store resolves it. Made in the repo: it has an identity, a clone none.
        foreign = git(root, "commit-tree", git(root, "rev-parse", "main^{tree}"),
                      "-m", "foreign")

        def scribbles(prompt, *, account, cwd, files, tools, denies, guard, effort="",
                      resume="", model=""):
            fakes.calls.append(f"build:{account}")
            found = subprocess.run(("git", "-C", cwd, "rev-parse", "--git-path",
                                    "refs/heads/main"), capture_output=True, text=True,
                                   check=True).stdout.strip()
            (pathlib.Path(cwd) / found).write_text(foreign + "\n")
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            return Outcome("ok", text="done")

        loop = Loop(repo=root, backlog=book, space=space, build=scribbles,
                   review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(base, git(root, "rev-parse", "main"))          # main never moved


class OriginPushEscapeTest(unittest.TestCase):
    def test_a_push_by_the_origin_name_never_reaches_the_repo(self):
        # `create` clones with `origin` still set to the repo. `git push`
        # writes the REMOTE's ref before its own local bookkeeping, so the
        # hook here — which only sees that last, local step — used to refuse
        # the push after the repo already had the ref. Removing `origin`
        # closes it: no remote by that name, so the push never leaves the
        # checkout at all.
        fakes = Fakes()
        by_name = {}

        root, book, space = repo_with(task())

        def pushes_by_name(prompt, *, account, cwd, files, tools, denies, guard,
                           effort="", resume="", model=""):
            fakes.calls.append(f"build:{account}")
            done = subprocess.run(("git", "-C", cwd, "push", "origin",
                                   "HEAD:refs/heads/escaped"), capture_output=True, text=True,
                                  check=False)
            by_name["returncode"], by_name["stderr"] = done.returncode, done.stderr
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            return Outcome("ok", text="done")

        loop = Loop(repo=root, backlog=book, space=space, build=pushes_by_name,
                   review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertNotEqual(0, by_name["returncode"])
        self.assertEqual("", git(root, "for-each-ref", "refs/heads/escaped"),
                         by_name["stderr"])

    def test_a_push_by_the_repos_own_path_is_stopped_by_the_tool_fence_not_the_hook(self):
        # Belt and braces: a push addressed by the repo's filesystem PATH needs
        # no `origin` remote, so removing it does not touch this one. The push
        # lands on the repo's own receive-pack, which runs the REPO's hooks —
        # never this checkout's `core.hooksPath`. Read what actually happens:
        # it succeeds, and the ref lands in the repo. `receive.denyCurrentBranch`
        # does not close this — it guards only the checked-out branch (main),
        # and this pushes a NEW one. The fence is the loop's own: `builder_denies`
        # denies `Bash(git push *)` to every builder (`lib/tools.py`, proven in
        # test_tools_denies.py), so the attempt never reaches a shell. This test
        # bypasses that fence on purpose to show what a raw push would do beneath it.
        fakes = Fakes()
        by_path = {}

        root, book, space = repo_with(task())

        def pushes_by_path(prompt, *, account, cwd, files, tools, denies, guard,
                           effort="", resume="", model=""):
            fakes.calls.append(f"build:{account}")
            done = subprocess.run(("git", "-C", cwd, "push", root,
                                   "HEAD:refs/heads/escaped2"), capture_output=True, text=True,
                                  check=False)
            by_path["returncode"] = done.returncode
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            return Outcome("ok", text="done")

        loop = Loop(repo=root, backlog=book, space=space, build=pushes_by_path,
                   review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(0, by_path["returncode"])
        self.assertNotEqual("", git(root, "for-each-ref", "refs/heads/escaped2"))


class LinkedWorktreeReuseTest(unittest.TestCase):
    def test_reuse_never_adopts_a_linked_worktree_or_touches_the_source_config(self):
        # A linked worktree (`git worktree add`, how `create` cut checkouts
        # before this change) shares refs with the repo by construction — no
        # push, no hook needed, refs are just the same refs. `reuse` writing
        # its hook config into one is worse still: `.git` there is a FILE, so
        # a plain `git config` resolves to the REPO's own shared config and
        # writes the driver's hooksPath into it. Adopting one would defeat
        # everything the rest of this file proves. Treat it as lost instead.
        root = repo_with(task())[0]
        linked = tempfile.mkdtemp()
        subprocess.run(("git", "-C", root, "worktree", "add", "--detach", linked, "HEAD"),
                       capture_output=True, check=True)
        config = pathlib.Path(root) / ".git" / "config"
        before = config.read_bytes()

        tree = Worktree(root, "T1", "HEAD").reuse(linked)

        self.assertEqual(before, config.read_bytes(), config.read_text())  # source config: untouched
        self.assertNotEqual(linked, tree.path)                        # not adopted
        self.assertTrue((pathlib.Path(tree.path) / ".git").is_dir())  # a fresh clone instead


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
