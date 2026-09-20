"""A pending-keep receipt is not thrown away because git could not answer.

`pending()` asks `git merge-base --is-ancestor`. Exit 1 is git's own "no, the
branch does not hold this commit", and only that makes the receipt stale. Any
other non-zero is an ERROR — a broken object store, a repository git will not
open — and reading it as "not an ancestor" deleted the one record that recovers
a keep whose card-write never ran (astra's round-4 finding 7). `advance` next
door already spells the rule out; this is the same call one file away.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import keep_pending
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

EXPECTED_TESTS = 1
BRANCH = "campaign/test"


def repo_with_a_receipt() -> tuple[str, pathlib.Path]:
    root = tempfile.mkdtemp()
    for args in (("git", "init", "-q", "-b", "main"),
                 ("git", "config", "user.email", "t@example.test"),
                 ("git", "config", "user.name", "test")):
        subprocess.run(args, cwd=root, capture_output=True, check=True)
    (pathlib.Path(root) / "a.py").write_text("one\n")
    subprocess.run(("git", "add", "-A"), cwd=root, capture_output=True, check=True)
    subprocess.run(("git", "commit", "-qm", "first"), cwd=root, capture_output=True, check=True)
    sha = subprocess.run(("git", "-C", root, "rev-parse", "HEAD"),
                         capture_output=True, text=True, check=True).stdout.strip()
    return root, keep_pending.note(root, BRANCH, "T1", sha)


class UnreadableCheckTest(unittest.TestCase):
    def test_a_read_error_keeps_the_receipt_and_reports_none(self):
        """Exit 128 is not a verdict. The receipt stays for the next turn to
        read, and this turn hands back nothing — a receipt returned would let
        `reconcile` mark the card done on a commit nobody proved the branch
        holds."""
        root, note = repo_with_a_receipt()
        unreadable = subprocess.CompletedProcess((), 128, b"", b"fatal: bad object")
        with mock.patch.object(keep_pending.subprocess, "run", return_value=unreadable):
            self.assertEqual([], keep_pending.pending(root, BRANCH))
        self.assertTrue(note.exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
