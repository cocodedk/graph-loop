"""The slicer's clean checkout takes its temp parent with it. One
`slice-repo-*` directory per planning call stayed behind — the checkout was
removed by `git worktree remove`, the mkdtemp parent that held it never was —
and /tmp filling on 2026-09-03 killed every process on the host. The rig is
`test_turn_slice`'s."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import slice_turn
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_turn_slice import router, space, tree_with

EXPECTED_TESTS = 2


def parents() -> set[str]:
    return {str(p) for p in pathlib.Path(tempfile.gettempdir()).glob("slice-repo-*")}


def wall():
    return tree_with({"id": "T1", "status": "needs_slice", "goal": "g",
                      "files": ["app.py"], "triage": "work",
                      "refused_why": "the gate said why"})


class CheckoutParentTest(unittest.TestCase):
    def test_a_finished_slice_leaves_no_checkout_parent(self):
        before = parents()
        route = router(unittest.mock.Mock(returncode=0, stdout="published: T1.fix", stderr=""))
        with unittest.mock.patch("subprocess.run", side_effect=route):
            slice_turn.slice_pending(wall(), space())
        self.assertEqual(before, parents())

    def test_a_checkout_that_cannot_be_made_leaves_no_parent(self):
        before = parents()
        route = router(unittest.mock.Mock(returncode=0, stdout="published: T1.fix", stderr=""))

        def add_fails(argv, **kw):
            if argv[0] == "git" and "add" in argv:
                return unittest.mock.Mock(returncode=1, stdout="", stderr="no worktree")
            return route(argv, **kw)

        s = space()
        with unittest.mock.patch("subprocess.run", side_effect=add_fails):
            slice_turn.slice_pending(wall(), s)
        self.assertIn("slice_skipped", [e.get("kind") for e in s.events()])
        self.assertEqual(before, parents())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
