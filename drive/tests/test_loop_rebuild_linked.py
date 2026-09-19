"""The kept-tree pick must agree with `Worktree.reuse` about what counts as a
real worktree to carry on in: a `.git` FILE — a linked worktree, cut by `git
worktree add` before checkouts became private clones — is not one. `reuse`
already refuses to adopt it and cuts a fresh clone instead; this proves
`loop.py`'s own pick agrees, treating the round as LOST rather than
in-place: the red-first proof and the contract review both run again, and
`rebuild_from`/`session` are not left pointing at the abandoned path.
Sibling of `test_loop_rebuild` at the 200-line cap.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import Outcome
from test_loop import Fakes, loop_for, task

EXPECTED_TESTS = 2


class LinkedWorktreeIsLostTest(unittest.TestCase):
    def test_a_rebuild_from_a_linked_worktree_starts_the_proofs_over(self):
        fakes = Fakes(review=[Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="REJECT", text="1. wrong line"),
                              Outcome("ok", verdict="ACCEPT", text="ok"),
                              Outcome("ok", verdict="ACCEPT", text="ok")])
        loop, book, space = loop_for(task(), fakes)
        first = loop.run_task(book.task("T1"))
        self.assertEqual("rejected", first.state)   # round one, for real: contract_seen is genuinely stamped

        # A linked worktree — how `create` cut checkouts before the private-clone
        # change — put in place of round one's own tree, carrying its session.
        linked = tempfile.mkdtemp()
        subprocess.run(("git", "-C", loop.repo, "worktree", "add", "--detach", linked, "HEAD"),
                       capture_output=True, check=True)
        config = pathlib.Path(loop.repo) / ".git" / "config"
        before = config.read_bytes()
        book.set_status("T1", "todo", rebuild_from=linked, session="sess-1")

        calls_before = list(fakes.calls)
        again = loop.run_task(book.task("T1"))

        self.assertEqual("done", again.state, again.why)
        # A true in-place round (contract_seen matches, in_place True) would skip
        # the contract review: ["build:work", "review"]. A lost round proves both.
        self.assertEqual(["review", "build:work", "review"], fakes.calls[len(calls_before):])
        rows = [row for row in space.events() if row.get("task") == "T1"]
        self.assertIn("rebuild_lost", [row["kind"] for row in rows])
        self.assertNotIn("rebuild", [row["kind"] for row in rows])   # never the in-place event
        cut = [row["path"] for row in rows if row["kind"] == "worktree"][-1]
        self.assertNotEqual(linked, cut)                    # a fresh clone, not the linked path
        self.assertTrue((pathlib.Path(cut) / ".git").is_dir())
        self.assertEqual(before, config.read_bytes())       # the source repo's own config: untouched
        queued = book.task("T1")
        self.assertEqual(again.worktree, queued["rebuild_from"])   # the replacement, never the linked path
        self.assertEqual(cut, queued["rebuild_from"])
        self.assertEqual("", queued["session"])                     # round one's session does not resume


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
