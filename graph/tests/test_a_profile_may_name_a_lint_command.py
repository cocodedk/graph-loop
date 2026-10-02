"""A profile may name a `## lint_command`, run before the suite (issue 288: it takes seconds, the suite minutes) and
the reviewer: a red lint is a red suite (issue 244; four of eleven builds reached CI red on lint alone). The suite, the lint, the reviewer and the
builder are faked."""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean
import lean_body
import lean_lint
import lean_run
import lean_spec
import tmp_root  # noqa: F401
from providers import Outcome
from test_lean import PROFILE_TEXT
from workspace import Workspace

EXPECTED_TESTS = 10
ACCEPT = Outcome("ok", verdict="ACCEPT", text="")
SUITE, LINT = "run-the-suite", "run-the-lint"


class Tree:
    """A worktree that is only a name for what the builder last wrote."""
    commit = "base"

    def __init__(self):
        self.path, self.state = tempfile.mkdtemp(), "first"

    def diff(self, binary=False, against=""):
        return f"diff --git a/guard.py b/guard.py\n+{self.state}\n"

    def keep(self, why):
        return self.path


class Rig(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())
        self.ran, self.mails = [], []

    def masked(self, suite=True, lint=True, output="E501 line too long"):
        def run(ws, command, cwd):
            self.ran.append(command)
            passed = suite if command == SUITE else lint
            return passed, "" if passed else output
        return run

    def check(self, command, **fakes):
        with mock.patch.object(lean_run, "masked", self.masked(**fakes)), \
                mock.patch.object(lean_run, "judge", return_value=ACCEPT) as judge:
            why, verdict = lean_run.check(self.ws, "rest-ring", "spec", Tree(), Outcome("ok"), command, 1)
        return why, verdict, judge

    def lint_events(self):
        return [row for row in self.ws.events() if row["kind"] == "lean_lint"]


class Reading(unittest.TestCase):
    def read(self, text):
        path = pathlib.Path(tempfile.mkdtemp()) / "profile-test.md"
        path.write_text(text)
        return lean.read_profile(str(path))

    def test_the_heading_and_its_first_indented_line_give_the_command(self):
        profile = self.read(f"{PROFILE_TEXT}\n## lint_command\n\n    ruff check .\n    never this\n")
        self.assertEqual("ruff check .", profile["lint_command"])
        self.assertEqual("./run-tests --all", profile["suite_command"])

    def test_no_heading_or_no_indented_line_gives_none_and_is_no_error(self):
        self.assertNotIn("lint_command", self.read(PROFILE_TEXT))
        self.assertNotIn("lint_command", self.read(f"{PROFILE_TEXT}\n## lint_command\n\nProse only.\n"))


class Check(Rig):
    def test_without_a_lint_command_the_suite_and_the_reviewer_decide_as_before(self):
        why, verdict, judge = self.check(SUITE)
        self.assertEqual(("", ACCEPT), (why, verdict))
        judge.assert_called_once()
        why, verdict, judge = self.check(SUITE, suite=False)
        self.assertEqual(("Fix the red suite: the failure is shown below. Check your fix with the failing test or this card's gate; the loop runs the full suite after you.\nE501 line too long", None), (why, verdict))
        judge.assert_not_called()
        self.assertEqual([SUITE] * 2, self.ran)
        self.assertEqual([], self.lint_events())
        with mock.patch.object(lean_run, "masked", self.masked()), \
                mock.patch.object(lean_run, "judge", return_value=Outcome("ok", verdict="REJECT", text="no test")):
            why, _ = lean_run.check(self.ws, "rest-ring", "spec", Tree(), Outcome("ok"), SUITE, 1)
        self.assertEqual("Fix what the reviewer refused (ok, REJECT): no test", why)

    def test_a_green_lint_lets_the_reviewer_be_asked(self):
        why, verdict, judge = self.check(lean_lint.Commands(SUITE, LINT))
        self.assertEqual(("", ACCEPT), (why, verdict))
        judge.assert_called_once()
        self.assertEqual([LINT, SUITE], self.ran)
        (event,) = self.lint_events()
        self.assertEqual(("rest-ring", 1, True), (event["task"], event["round"], event["passed"]))

    def test_a_red_lint_returns_its_reason_and_the_reviewer_is_not_asked(self):
        why, verdict, judge = self.check(lean_lint.Commands(SUITE, LINT), lint=False)
        self.assertEqual((f"Fix the red lint. Run {LINT}, then fix the findings shown below:\nE501 line too long", None), (why, verdict))
        judge.assert_not_called()
        self.assertEqual([LINT], self.ran)   # the suite, minutes long, never ran
        (event,) = self.lint_events()
        self.assertEqual((False, "E501 line too long"), (event["passed"], event["tail"]))

    def test_the_reason_keeps_the_gates_excerpt_whole_and_the_event_its_last_2000_characters(self):
        long = "head" + "x" * 1996 + "tail"
        why, _, _ = self.check(lean_lint.Commands(SUITE, LINT), lint=False, output=long)
        self.assertEqual(f"Fix the red lint. Run {LINT}, then fix the findings shown below:\n" + long, why)   # never cut twice
        self.assertEqual(long[-2000:], self.lint_events()[0]["tail"])
        why, _, _ = self.check(lean_lint.Commands(SUITE, LINT), lint=False, output="short")
        self.assertTrue(why.endswith(":\nshort"))

    def test_a_red_suite_follows_a_green_lint(self):
        why, _, _ = self.check(lean_lint.Commands(SUITE, LINT), suite=False)
        self.assertTrue(why.startswith("Fix the red suite"))
        self.assertEqual([LINT, SUITE], self.ran)
        self.assertEqual([True], [row["passed"] for row in self.lint_events()])


class Repairs(Rig):
    def run_it(self, writes):
        queue, self.prompts, tree = list(writes), [], Tree()

        def build(ws, task, prompt, tree, resume="", effort=""):
            self.prompts.append(prompt)
            tree.state = queue.pop(0) if queue else tree.state
            return Outcome("ok", session="s1")
        spec = pathlib.Path(tempfile.mkdtemp()) / "rest ring.md"
        spec.write_text("Show the overdue rest ring in amber.\n")
        profile = {"suite_command": SUITE, "lint_command": LINT}
        with mock.patch.object(lean_spec, "start", return_value=(tree, "")), \
                mock.patch.object(lean_run, "build", build), \
                mock.patch.object(lean_run, "masked", self.masked(lint=False)), \
                mock.patch.object(lean_run, "judge") as judge, \
                mock.patch.object(lean_run, "mail", lambda ws, subject, body: self.mails.append(body)):
            url = lean_run.run_feature(self.ws, "repo", str(spec), profile, "profile.md")
        judge.assert_not_called()
        return url

    def test_a_red_lint_repairs_with_its_reason_at_most_twice_then_stops(self):
        self.assertEqual("", self.run_it(["a", "b", "c"]))
        self.assertEqual(1 + lean_run.REPAIRS, len(self.prompts))
        self.assertIn(f"Fix the red lint. Run {LINT}, then fix the findings shown below:\nE501 line too long", self.prompts[1])
        self.assertEqual([LINT] * 3, self.ran)
        self.assertEqual("lean_stopped", self.ws.events()[-1]["kind"])

    def test_a_repair_that_changes_nothing_stops_the_run(self):
        self.assertEqual("", self.run_it(["a"]))
        self.assertEqual(2, len(self.prompts))
        self.assertIn("The repair changed nothing", self.ws.events()[-1]["why"])


class Prompt(unittest.TestCase):
    def test_the_builder_is_told_the_lint_command_and_without_one_the_prompt_is_unchanged(self):
        plain = lean_body.builder_prompt("spec", "gate.sh", "profile.md", "", False)
        told = lean_body.builder_prompt("spec", "gate.sh", "profile.md", "", False, "", LINT)
        self.assertIn(f"runs `{LINT}` before the suite", told)
        self.assertNotIn("lint", plain)
        self.assertEqual(plain, told.replace(told[told.index(" The loop also"):told.index("\n\n## Spec")], ""))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
