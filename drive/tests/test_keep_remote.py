"""`keep_remote`'s own edge cases: a push failure that prints nothing, and
whether the local branch and its remote copy agree.

Kept apart from `test_keep.py` (already at its own 200-line cap) —
`test_push_with_no_remote_fails_without_raising` there covers the ordinary
failure path, where git itself has something to say on stderr.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from keep_remote import behind, push

EXPECTED_TESTS = 4


def _repo(branch: str = "campaign/test") -> str:
    root = tempfile.mkdtemp()
    for args in (("git", "init", "-q", "-b", branch),
                 ("git", "config", "user.email", "t@example.test"),
                 ("git", "config", "user.name", "test")):
        subprocess.run(args, cwd=root, capture_output=True, check=True)
    (pathlib.Path(root) / "a.py").write_text("one\n")
    subprocess.run(("git", "add", "-A"), cwd=root, capture_output=True, check=True)
    subprocess.run(("git", "commit", "-qm", "first"), cwd=root, capture_output=True, check=True)
    return root


class PushRemoteTest(unittest.TestCase):
    def test_a_nonzero_exit_with_no_stderr_still_reports_failure(self):
        silent = unittest.mock.Mock(returncode=1, stdout="", stderr="")
        with unittest.mock.patch("subprocess.run", return_value=silent):
            failed = push("/repo", "campaign/test", "origin")
        self.assertTrue(failed)
        self.assertIn("exited 1", failed)


class BehindTest(unittest.TestCase):
    def test_behind_is_false_right_after_a_push_and_true_after_a_new_commit(self):
        root = _repo()
        bare = tempfile.mkdtemp()
        subprocess.run(("git", "init", "-q", "--bare", bare), capture_output=True, check=True)
        subprocess.run(("git", "-C", root, "remote", "add", "origin", bare),
                       capture_output=True, check=True)
        self.assertEqual("", push(root, "campaign/test", "origin"))
        self.assertFalse(behind(root, "campaign/test"))
        (pathlib.Path(root) / "a.py").write_text("two\n")
        subprocess.run(("git", "add", "-A"), cwd=root, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "second"), cwd=root, capture_output=True, check=True)
        self.assertTrue(behind(root, "campaign/test"))

    def test_behind_is_true_with_no_remote_configured_at_all(self):
        root = _repo()
        self.assertTrue(behind(root, "campaign/test"))   # local exists, remote ref absent

    def test_behind_is_false_when_the_remote_has_moved_ahead_of_the_local_tip(self):
        root = _repo()
        bare = tempfile.mkdtemp()
        subprocess.run(("git", "init", "-q", "--bare", bare), capture_output=True, check=True)
        subprocess.run(("git", "-C", root, "remote", "add", "origin", bare),
                       capture_output=True, check=True)
        self.assertEqual("", push(root, "campaign/test", "origin"))
        clone = tempfile.mkdtemp()
        subprocess.run(("git", "clone", "-q", "-b", "campaign/test", bare, clone),
                       capture_output=True, check=True)
        for args in (("git", "config", "user.email", "t@example.test"),
                     ("git", "config", "user.name", "test")):
            subprocess.run(args, cwd=clone, capture_output=True, check=True)
        (pathlib.Path(clone) / "b.py").write_text("ahead\n")
        subprocess.run(("git", "add", "-A"), cwd=clone, capture_output=True, check=True)
        subprocess.run(("git", "commit", "-qm", "ahead on origin"), cwd=clone,
                       capture_output=True, check=True)
        subprocess.run(("git", "push", "-q", "origin", "campaign/test"), cwd=clone,
                       capture_output=True, check=True)
        subprocess.run(("git", "-C", root, "fetch", "-q", "origin"), capture_output=True, check=True)
        # origin is ahead of root's tip but still contains it — not behind.
        self.assertFalse(behind(root, "campaign/test"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
