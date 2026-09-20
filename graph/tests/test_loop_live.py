"""Live tasks: what their builders may run, and what their prompts say. The
rig lives in `test_loop`."""

from __future__ import annotations

import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
os.environ.setdefault("GRAPH_HELPER", "/repo/bin/sc")   # the repository's own command tool
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from providers import Outcome
from test_loop import Fakes, loop_for, task
from tools import (
    LIVE_VERBS,
    builder_denies,
    builder_guard,
    builder_tools,
    guard_files,
    helper,
    helper_commands,
)

HELPER = helper()
EXPECTED_TESTS = 10


class BuilderToolsTest(unittest.TestCase):
    """A live builder's allowlist IS the boundary: no shell at all, only the
    helper by the main checkout's absolute path (never a worktree copy it could
    edit), and Edit/Write only on its own files. A code task keeps the shell its
    own gate names, never a fixed language's stack."""

    def test_a_live_task_gets_its_exact_commands_and_no_shell(self):
        row = task(gate_has_side_effects=True, files=["state/x.txt"],
                   helper_verbs=["free prd-app-04", "journal", "newpkg 9 x", "story x\nrebuild *", "why; ls",
                                 "run", "reset-target", "rebuild"])   # bare verbs whose argument the contract must fix
        tools = builder_tools(row)
        # bound = the whole command; bare = open; never newpkg; no newline or control character adds an entry
        self.assertEqual([f"{HELPER} free prd-app-04", f"{HELPER} journal *"], helper_commands(row))
        self.assertEqual(f"Read,Grep,Glob,Edit(state/x.txt),Bash({HELPER} free prd-app-04),"
                         f"Bash({HELPER} journal *),Bash(cat *),Bash(ls *),Bash(head *),Bash(tail *)", tools)
        self.assertTrue(builder_denies(row).startswith("Monitor,Workflow,"))   # tools that run commands of their own
        self.assertTrue(HELPER.startswith("/"))                 # the main checkout, never a worktree copy
        self.assertTrue({"journal", "free"} <= set(LIVE_VERBS))
        self.assertNotIn(HELPER, builder_tools(task(gate_has_side_effects=True)))   # no verbs named, no helper at all
        for absent in ("newpkg", "Write(", "Edit,", "bash "):
            self.assertNotIn(absent, tools)
        self.assertEqual(f"{HELPER} free prd-app-04\n{HELPER} journal *\ncat *\nls *\nhead *\ntail *", builder_guard(row))
        self.assertEqual("", builder_guard(task()))
        self.assertIn("Bash(docker *)", builder_denies(row))       # the last fence, against an inherited allow
        self.assertIn("Bash(bash *)", builder_denies(row))
        self.assertEqual("Bash(git push *)", builder_denies(task()))   # a builder never pushes
        self.assertEqual([], helper_commands(task(gate_has_side_effects=True, helper_verbs=["reject"])))   # bound to finding+target
        # a bound verb needs ALL its arguments — the helper would otherwise fill one in
        self.assertEqual([], helper_commands(task(gate_has_side_effects=True, helper_verbs=["run FND-0001", "free", "reject FND-1"])))
        self.assertEqual([f"{HELPER} run FND-0001 dev-web-01", f"{HELPER} rebuild cli broker"],
                         helper_commands(task(gate_has_side_effects=True, helper_verbs=["run FND-0001 dev-web-01", "rebuild cli broker", "run FND-1 a b"])))
        self.assertEqual([f"{HELPER} reject FND-BASE-06 prd-db-02"],
                         helper_commands(task(gate_has_side_effects=True, helper_verbs=["reject FND-BASE-06 prd-db-02"])))
        self.assertEqual("/w/state/x.txt", guard_files(row, "/w"))     # the writers' whitelist, absolute in the worktree
        self.assertEqual("", guard_files(task(), "/w"))

    def test_a_code_task_keeps_its_shell(self):
        tools = builder_tools(task())
        self.assertIn("Bash(git *)", tools)                         # the base
        self.assertIn("Bash(grep *)", tools)                        # its own gate, no more
        self.assertNotIn(HELPER, tools)

    def test_a_card_creating_a_listed_file_gets_write(self):
        # T26.observed's builder finished the code and was then refused the very
        # test file the card ordered it to create: a listed file absent from the
        # builder's OWN worktree grants Write; one already there does not.
        import tempfile
        tree = tempfile.mkdtemp()
        self.assertIn("Write", builder_tools(task(files=["not-made-yet.py"]), tree))
        (pathlib.Path(tree) / "made.py").write_text("x")
        self.assertNotIn("Write", builder_tools(task(files=["made.py"]), tree))


class LiveBuilderTest(unittest.TestCase):
    """A task whose gate acts on the live stack is built WITH the stack, through
    the helper only: its prompt names the helper's verbs instead of forbidding
    the very containers the task names, and its tools (lib/tools.py) are the
    helper and nothing else. T2's builder was stopped by a footer saying
    "touch no container" on a task whose ruling was a volume reset."""

    def test_a_live_task_is_handed_the_scoped_helper_not_a_ban(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(gate_has_side_effects=True, gate="true", helper_verbs=["free prd-app-04", "journal"]), fakes)
        loop.run_task(book.task("T1"))
        self.assertNotIn("Touch no container", fakes.prompts[-1])
        self.assertIn(HELPER, fakes.prompts[-1])
        self.assertIn(f"`{HELPER} free prd-app-04`; `{HELPER} journal *`", fakes.prompts[-1])
        self.assertIn(f"{HELPER} <verb>", fakes.prompts[-1])
        self.assertIn("no docker, no curl, no python", fakes.prompts[-1])
        self.assertEqual(builder_tools(book.task("T1")), fakes.tools[-1])   # the exact live list reached the builder
        self.assertEqual(builder_denies(book.task("T1")), fakes.denies[-1])
        self.assertEqual(builder_guard(book.task("T1")), fakes.guards[-1])       # the guard's prefixes reached it too
        self.assertEqual(1, len(fakes.tools))    # a live builder that answers is called once; only a
        # refused session, which never reached the model, tries the other account (test_live_accounts)

    def test_a_code_task_keeps_the_container_ban(self):
        fakes = Fakes()
        loop, book, _ = loop_for(task(), fakes)
        loop.run_task(book.task("T1"))
        self.assertIn("Touch no container", fakes.prompts[-1])
        self.assertNotIn(HELPER, fakes.prompts[-1])


class LiveCallLostTest(unittest.TestCase):
    def test_a_live_call_that_did_not_return_goes_to_a_person_not_a_retry(self):
        # A limit or a crash is no proof the stack is untouched; a second call
        # would repeat a live action, and so would the next turn.
        fakes = Fakes()
        loop, book, space = loop_for(task(gate_has_side_effects=True, gate="true", helper_verbs=["journal"]), fakes,
                                     extra=[{"id": "T-live", "goal": "another live one", "status": "todo", "needs": [],
                                             "files": [], "gate": "true", "done_when": "x",
                                             "gate_has_side_effects": True, "helper_verbs": ["journal"]},
                                            {"id": "T-code", "goal": "a code one", "status": "todo", "needs": [],
                                             "files": ["a.py"], "gate": "true", "done_when": "x"}])
        calls = []
        # A limit that spent tokens: the call reached the model and may have run a helper
        # verb. A limit refused before the first turn is proved harmless and falls through
        # to the other account instead (test_live_accounts).
        loop.build = lambda prompt, **kw: calls.append(1) or Outcome(
            "limit", text="usage limit", cost=0.5, tokens=800)
        out = loop.run_task(book.task("T1"))
        self.assertEqual(1, len(calls))
        self.assertEqual("blocked", out.state)
        self.assertEqual("live_call_lost", book.task("T1")["status"])
        self.assertIn("half-done", book.task("T1")["refused_why"])
        self.assertTrue(any("half-done" in line for line in space.alerts()))
        self.assertTrue(any(r.get("kind") == "needs_a_person" and r.get("task") == "T1" for r in space.events()))
        # every other live task waits for the person too: the stack is in doubt, not just this task
        held = [row for row in book.tasks() if row.get("status") == "held"]
        self.assertEqual(["T-live"], [row["id"] for row in held])
        self.assertIn("live call", held[0]["refused_why"])   # held the moment the call opened


class LiveCallOpenTest(unittest.TestCase):
    def test_a_live_task_is_marked_before_its_call_not_after(self):
        # A driver death mid-call would otherwise leave the task todo and the
        # next turn would repeat run/declare/reset-target.
        fakes = Fakes()
        loop, book, _ = loop_for(task(gate_has_side_effects=True, gate="true", helper_verbs=["journal"]), fakes)
        seen = {}
        def build(prompt, **kw):
            seen["status"] = book.task("T1")["status"]        # what the backlog says DURING the call
            raise RuntimeError("the driver died here")
        loop.build = build
        with self.assertRaises(RuntimeError):
            loop.run_task(book.task("T1"))
        self.assertEqual("live_call_open", seen["status"])
        self.assertEqual("live_call_open", book.task("T1")["status"])   # and it stays, not todo

    def test_a_session_is_recorded_without_reverting_live_call_open_to_todo(self):
        # task.get("status") is the picked-time "todo": a write keyed on it undoes live_call_open.
        from loop_steps import build as build_step
        from worktree import Worktree
        loop, book, _ = loop_for(task(gate_has_side_effects=True, gate="true", helper_verbs=["journal"]), Fakes())
        loop.build = lambda prompt, **kw: Outcome("ok", text="done", cost=1, tokens=100, session="sess-42")
        stopped = build_step(loop, book.task("T1"), Worktree(loop.repo, "T1", loop.commit).create(), False)
        self.assertIsNone(stopped)   # ready for the gate, not ended
        self.assertEqual(("live_call_open", "sess-42"), (book.task("T1")["status"], book.task("T1")["session"]))


class LiveTurnEndedTest(unittest.TestCase):
    def test_a_live_turn_that_ends_badly_waits_for_a_person(self):
        # The stack moved. A failed gate or a rejected diff must not send the
        # next turn to repeat run/declare/reset-target on it.
        fakes = Fakes()
        loop, book, _ = loop_for(task(gate_has_side_effects=True, gate="false", helper_verbs=["journal"]), fakes)
        out = loop.run_task(book.task("T1"))
        self.assertEqual("failed", out.state)
        row = book.task("T1")
        self.assertEqual("live_turn_ended", row["status"])
        self.assertTrue(row["blocked_by_human"])
        self.assertIn("a live call was made", row["refused_why"])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
