"""The loop itself: what it runs, what it refuses, and when it stops.

Written before `loop.py`, against fake providers — no model is called here. Each
case drives one task through `run_task` and reads the campaign's own record for
what happened.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
import yaml  # type: ignore[import-untyped]  # no stubs in this environment
from backlog import Backlog
from loop import Loop
from providers import Outcome
from workspace import Workspace

EXPECTED_TESTS = 8


def repo_with(task: dict, extra: list | None = None) -> tuple[str, Backlog, Workspace]:
    root = tempfile.mkdtemp()
    for args in (("git", "init", "-q", "-b", "main"),
                 ("git", "config", "user.email", "t@example.test"),
                 ("git", "config", "user.name", "test")):
        subprocess.run(args, cwd=root, capture_output=True, check=True)
    (pathlib.Path(root) / "a.py").write_text("one\n")
    (pathlib.Path(root) / "backlog.yaml").write_text(
        yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": [task] + list(extra or [])}, sort_keys=False))
    subprocess.run(("git", "add", "-A"), cwd=root, capture_output=True, check=True)
    subprocess.run(("git", "commit", "-qm", "first"), cwd=root, capture_output=True,
                   check=True)
    book = Backlog(pathlib.Path(root) / "backlog.yaml")
    space = Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog=str(book.path))
    return root, book, space


def task(**extra) -> dict:
    row = {"id": "T1", "goal": "make a.py say two", "status": "todo", "needs": [],
           "files": ["a.py"], "gate": "grep -q two a.py",
           "expect_red": "", "done_when": "a.py says two"}
    row.update(extra)
    return row


class Fakes:
    """Stand-ins for the two providers, scripted per call."""

    def __init__(self, build=None, review=None, edit="two\n"):
        self.build = build or [Outcome("ok", text="done", cost=0.1, tokens=10)]
        self.review = review or [Outcome("ok", verdict="ACCEPT", text="REVIEW: ACCEPT"),
                                 Outcome("ok", verdict="ACCEPT", text="REVIEW: ACCEPT")]
        self.edit = edit
        self.calls: list[str] = []
        self.prompts: list[str] = []
        self.tools: list[str] = []
        self.denies: list[str] = []
        self.guards: list[str] = []
        self.resumes: list[str] = []
        self.cwds: list[str] = []
        self.review_task_ids: list[str] = []

    def builder(self, prompt, *, account, cwd, files, tools, denies, guard, effort="", resume="",
                model=""):
        self.tools.append(tools); self.denies.append(denies); self.guards.append(guard)
        self.resumes.append(resume)
        self.calls.append(f"build:{account}")
        self.prompts.append(prompt)
        out = self.build.pop(0) if len(self.build) > 1 else self.build[0]
        # A refusal runs no tool, so the fake edits only when the call answered
        # — or the tree-snapshot witness reads every fake refusal as paid work.
        if self.edit is not None and out.kind == "ok":
            (pathlib.Path(cwd) / "a.py").write_text(self.edit)
        return out

    def reviewer(self, prompt, *, cwd="", effort="", space=None, task_id=""):
        self.calls.append("review")
        self.cwds.append(cwd)
        self.review_task_ids.append(task_id)
        out = self.review.pop(0) if len(self.review) > 1 else self.review[0]
        # Scripts use shorthand; the fake provider emits the real diff protocol.
        if "The numbered diff:" in prompt and out.ok and not out.text.lstrip().startswith("{"):
            anchor = next((int(line.split(":", 1)[0]) for line in prompt.splitlines()
                           if ": +" in line and ": +++" not in line), 1)
            findings = ([{"diff_line": anchor, "requirement": "done_when",
                         "problem": out.text, "evidence": "The changed line fails the scripted requirement"}]
                        if out.verdict == "REJECT" else [])
            out = dataclasses.replace(out, text=json.dumps({"review": out.verdict,
                                      "accept": out.verdict == "ACCEPT", "findings": findings,
                                      "observations": []}))
        return out


def loop_for(row: dict, fakes: Fakes, extra: list | None = None) -> tuple[Loop, Backlog, Workspace]:
    root, book, space = repo_with(row, extra)
    return Loop(repo=root, backlog=book, space=space, build=fakes.builder,
                review=fakes.reviewer), book, space


class HappyPathTest(unittest.TestCase):
    def test_a_task_is_reviewed_built_gated_reviewed_and_marked_done(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(triage="work"), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual(["review", "build:work", "review"], fakes.calls)
        self.assertEqual("done", book.task("T1")["status"])
        self.assertNotIn("triage", book.task("T1"))

    def test_already_delivered_work_needs_no_builder(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(gate="true"), fakes)   # green from the start
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state)
        self.assertIn("already delivered", out.why)
        self.assertEqual([], fakes.calls)

    def test_a_rejected_contract_never_reaches_a_builder(self):
        fakes = Fakes(review=[Outcome("ok", verdict="REJECT", text="1. too broad")])
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("refused", out.state)
        self.assertEqual(["review"], fakes.calls)


class RefusalTest(unittest.TestCase):
    def test_a_builder_that_writes_outside_its_files_is_refused(self):
        fakes = Fakes()

        def wander(prompt, *, account, cwd, files, tools, denies, guard, effort="", resume="", model=""):
            fakes.calls.append(f"build:{account}")
            (pathlib.Path(cwd) / "a.py").write_text("two\n")
            (pathlib.Path(cwd) / "elsewhere.py").write_text("not mine\n")
            return Outcome("ok", text="done")

        loop, book, _ = loop_for(task(), fakes)
        loop.build = wander
        out = loop.run_task(book.task("T1"))
        self.assertEqual("failed", out.state)
        self.assertIn("elsewhere.py", out.why)

    def test_a_failed_gate_is_a_failure_and_keeps_the_worktree(self):
        fakes = Fakes(edit="still one\n")
        loop, book, _ = loop_for(task(), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("failed", out.state)
        self.assertTrue(pathlib.Path(out.worktree).exists())


class PushTest(unittest.TestCase):
    def test_a_kept_card_with_no_remote_still_finishes_done_and_alerts(self):
        # No remote configured: the push fails, but the keep already stands —
        # the card is done, and the failure is only an alert, not a loss.
        fakes = Fakes()
        root, book, space = repo_with(task(triage="work"))
        loop = Loop(repo=root, backlog=book, space=space, build=fakes.builder,
                    review=fakes.reviewer, branch="campaign/test")
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertTrue(book.task("T1").get("commit"))
        self.assertNotIn("triage", book.task("T1"))
        self.assertTrue(any("not pushed" in line for line in space.alerts(unread_only=False)))


class ReviewCwdTest(unittest.TestCase):
    def test_both_reviews_run_in_the_worktree_not_the_repo_root(self):
        fakes = Fakes()
        root, book, space = repo_with(task())
        loop = Loop(repo=root, backlog=book, space=space, build=fakes.builder,
                    review=fakes.reviewer)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("done", out.state, out.why)
        self.assertEqual([out.worktree, out.worktree], fakes.cwds)
        self.assertNotEqual(root, out.worktree)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
