"""The loop resolves the review threads its accepted revise round fixed (issue #258).

After a repair round fixed what a reviewer raised, the thread stayed open and a person replied "fixed at
head <sha>" and resolved it by hand. The loop's own reviewer accepts a revise round only after checking that
the change fixes each thread, so an accepted round replies and resolves exactly the threads it started with;
a refused round, and a thread posted while the run worked, resolve nothing.
"""

import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_git
from providers import Outcome
from test_lean_run import Rig

EXPECTED_TESTS = 6
URL = "https://example.test/pull/1"


def gh(*results):
    """A fake `subprocess.run` for gh: each call gets the next returncode; its calls are kept."""
    codes = list(results)

    def run(command, **_):
        run.calls.append(command)
        return subprocess.CompletedProcess(command, codes.pop(0) if codes else 0, "{}", "")
    run.calls = []
    return run


class Reading(unittest.TestCase):
    def test_the_threads_read_carry_their_ids(self):
        nodes = [{"id": "T_old", "isResolved": True, "comments": {"nodes": [{"path": "a.py", "line": 1, "body": "old"}]}},
                 {"id": "T_1", "isResolved": False, "comments": {"nodes": [{"path": "b.py", "line": 2, "body": "fix b"}]}}]
        answer = json.dumps({"data": {"resource": {"reviewThreads": {"nodes": nodes}}}})
        done = subprocess.CompletedProcess((), 0, stdout=answer, stderr="")
        with mock.patch.object(lean_git.subprocess, "run", return_value=done):
            found = lean_git.threads(URL)
        self.assertEqual(("b.py:2\nfix b", ("T_1",)), (str(found), found.ids))


class Resolving(unittest.TestCase):
    def test_each_thread_gets_a_reply_with_the_head_and_is_resolved(self):
        run = gh()
        with mock.patch.object(lean_git.subprocess, "run", run):
            self.assertEqual(2, lean_git.resolve(("T_1", "T_2"), "0123456789abcdef"))
        self.assertEqual(2, len(run.calls))
        self.assertIn("t=T_1", run.calls[0])
        self.assertIn("b=fixed at head 0123456789ab", run.calls[0])
        self.assertTrue(any("resolveReviewThread" in part for part in run.calls[0]))

    def test_no_threads_means_no_call(self):
        run = gh()
        with mock.patch.object(lean_git.subprocess, "run", run):
            self.assertEqual(0, lean_git.resolve((), "abc"))
        self.assertEqual([], run.calls)

    def test_a_thread_that_will_not_resolve_is_left_for_a_person_and_not_counted(self):
        with mock.patch.object(lean_git.subprocess, "run", gh(1, 0)):
            self.assertEqual(1, lean_git.resolve(("T_1", "T_2"), "abc"))


class Round(Rig):
    def revise(self, reviews):
        url = self.run_it(self.builder(("ring.py", "amber\n")))
        subprocess.run(("git", "-C", self.repo, "fetch", "-q", "origin"), check=True)
        threads = lean_git.Threads("ring.py:1\nBlock it.", ("T_1", "T_2"))
        with mock.patch.object(lean_git, "resolve", return_value=2) as resolve:
            self.run_it(self.builder(("guard.py", "block\n")), reviews=reviews, revise=threads, pr=url)
        return resolve

    def test_an_accepted_round_resolves_the_threads_it_started_with(self):
        resolve = self.revise((Outcome("ok", verdict="ACCEPT"),))
        resolve.assert_called_once()
        self.assertEqual(("T_1", "T_2"), resolve.call_args.args[0])
        row = next(r for r in self.ws.events() if r["kind"] == "lean_threads_resolved")
        self.assertEqual((2, 2), (row["resolved"], row["threads"]))

    def test_a_round_the_reviewer_still_refused_resolves_nothing(self):
        refused = Outcome("ok", verdict="REJECT", text="still wrong")
        resolve = self.revise((refused, refused, refused))
        resolve.assert_not_called()


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the six above and this one


if __name__ == "__main__":
    unittest.main()
