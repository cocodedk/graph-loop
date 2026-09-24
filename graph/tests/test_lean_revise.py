"""The lean loop revises its own open pull request: review threads in, a push to the
same branch out, and a reviewer who sees the whole feature. Git is real; the rest is faked."""

import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_git
from test_keep import sha
from test_lean_run import Rig, show


class Revise(Rig):
    def test_review_threads_are_fixed_on_the_same_pull_request(self):
        url = self.run_it(self.builder(("ring.py", "amber\n")))
        subprocess.run(("git", "-C", self.repo, "fetch", "-q", "origin"), check=True)
        tip = sha(self.origin, "refs/heads/lean/rest-ring")
        self.prompts.clear()
        again = self.run_it(self.builder(("guard.py", "block\n")),
                            revise="ring.py:1\nBlock an allow with an unsafe category.", pr=url)
        self.assertEqual(url, again)
        self.assertEqual(1, len(self.prs))                        # no second pull request
        self.assertIn("Block an allow with an unsafe category.", self.prompts[0])
        self.assertEqual("block\n", show(self.origin, "lean/rest-ring", "guard.py"))
        self.assertEqual("amber\n", show(self.origin, "lean/rest-ring", "ring.py"))
        parent = subprocess.run(("git", "-C", self.origin, "rev-parse", "lean/rest-ring^"),
                                capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(tip, parent)                             # a fast-forward of the PR
        self.assertIn("ring.py", self.reviews[-1])                # the whole feature is reviewed
        self.assertIn("guard.py", self.reviews[-1])
        self.assertEqual(self.base, sha(self.origin, "refs/heads/main"))


class Threads(unittest.TestCase):
    def test_only_unresolved_threads_are_read_without_their_folded_detail(self):
        nodes = [{"isResolved": True, "comments": {"nodes": [{"path": "a.py", "line": 1, "body": "old"}]}},
                 {"isResolved": False, "comments": {"nodes": [{"path": "jev.py", "line": 92,
                  "body": "**Block allow with a category.**\n<details>prompt for agents</details>"}]}}]
        answer = json.dumps({"data": {"resource": {"reviewThreads": {"nodes": nodes}}}})
        done = subprocess.CompletedProcess((), 0, stdout=answer, stderr="")
        with mock.patch.object(lean_git.subprocess, "run", return_value=done):
            text = lean_git.threads("https://example.test/pull/1")
        self.assertEqual("jev.py:92\n**Block allow with a category.**", text)


if __name__ == "__main__":
    unittest.main()
