"""A revise round is reviewed like a first build (issue 216): the suite passes, the reviewer reads the
round's diff with the review threads it answers, a refusal repairs, and the last refusal still pushes
with its findings in the pull request's description. The reviewer, the suite, git and `gh` are faked."""

import inspect
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_git
import lean_judge
import lean_run
import lean_spec
import tmp_root  # noqa: F401
from providers import Outcome
from review_scope import NOTED_VERDICT
from workspace import Workspace

EXPECTED_TESTS = 7
ROOT = pathlib.Path(__file__).resolve().parents[2]
THREADS = "ring.py:1\nBlock an allow with an unsafe category."
URL = "https://example.test/pull/1"
PROFILE = {"suite_command": "run-the-suite"}
ACCEPT = Outcome("ok", verdict="ACCEPT", text="")


def refused(text: str) -> Outcome:
    return Outcome("ok", verdict="REJECT", text=text)


class Tree:
    """A worktree that is only a name for what the builder last wrote."""
    commit = "base"

    def __init__(self):
        self.path, self.state = tempfile.mkdtemp(), ""

    def diff(self, binary=False, against=""):
        return f"diff --git a/guard.py b/guard.py\n+{self.state}\n" if self.state else ""

    def keep(self, why):
        return self.path

    def remove(self):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "rest ring.md"
        self.spec.write_text("Show the overdue rest ring in amber.\n")


class Revised(Base):
    def revise(self, writes, reviews, suites=(True,), description="The old description.\n"):
        """One revise run with git, `gh`, the builder, the suite and the reviewer faked."""
        queue, suites, reviews, tree = list(writes), list(suites), list(reviews), Tree()
        self.prompts, self.reviewed_prompts, self.git, self.gh, self.mails = [], [], [], [], []

        def build(ws, task, prompt, tree, resume="", effort=""):
            self.prompts.append(prompt)
            tree.state = queue.pop(0)
            return Outcome("ok", session="s1")

        def codex(_bin, prompt, **_kw):
            self.reviewed_prompts.append(prompt)
            return reviews.pop(0)

        def run(argv, *args, **kwargs):
            self.gh.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout=description, stderr="")
        with mock.patch.object(lean_spec, "start", return_value=(tree, "")), \
                mock.patch.object(lean_run, "build", build), \
                mock.patch.object(lean_run, "masked", lambda ws, command, cwd: (suites.pop(0), "")), \
                mock.patch.object(lean_run.review, "codex", codex), \
                mock.patch.object(lean_run, "mail", lambda ws, subject, body: self.mails.append(body)), \
                mock.patch.object(lean_git, "commit", return_value="work"), \
                mock.patch.object(lean_git, "git", lambda cwd, *args, **kw: self.git.append(args) or ""), \
                mock.patch.object(lean_git.subprocess, "run", run):
            return lean_run.run_feature(self.ws, "repo", str(self.spec), PROFILE, "profile.md",
                                        revise=THREADS, pr=URL)

    def reviewed(self):
        return [row for row in self.ws.events() if row["kind"] == "lean_review"]

    def pushed(self):
        return [args for args in self.git if args[0] == "push"]

    def test_a_revise_round_asks_the_reviewer_once_with_the_threads(self):
        self.assertEqual(URL, self.revise(["block"], (ACCEPT,)))
        (prompt,) = self.reviewed_prompts
        self.assertIn("## The review threads this round answers\n\n" + THREADS, prompt)
        self.assertIn("+block", prompt)                          # this round's change
        self.assertNotIn("## The diff against main", prompt)
        self.assertEqual(1, len(self.reviewed()))

    def test_an_accepted_round_pushes_and_its_event_carries_the_outcome(self):
        self.revise(["block"], (Outcome("ok", verdict="ACCEPT", text="a small note"),))
        event = self.reviewed()[-1]
        self.assertEqual(("rest-ring", 1, "ok", "ACCEPT", "a small note"),
                         (event["task"], event["round"], event["outcome"], event["verdict"], event["findings"]))
        self.assertEqual([("push", "--quiet", "origin", "work:refs/heads/lean/rest-ring")], self.pushed())
        self.assertEqual([], self.gh)                            # the description is left as it was

    def test_a_refused_round_repairs_twice_at_most_and_the_last_refusal_still_pushes(self):
        again = self.revise(["a", "b", "c"], [refused(f"finding {n}") for n in (1, 2, 3)], suites=(True, True, True),
                            description="    an indented code block\n")
        self.assertEqual(URL, again)
        self.assertEqual(1 + lean_run.REPAIRS, len(self.prompts))     # the revise build, two repairs
        self.assertEqual(3, len(self.reviewed_prompts))
        self.assertIn("finding 1", self.prompts[1])
        self.assertIn("finding 2", self.prompts[2])
        self.assertEqual(1, len(self.pushed()))
        (view, edit) = self.gh
        self.assertEqual("view", view[2])
        body = edit[edit.index("--body") + 1]
        self.assertTrue(body.startswith("    an indented code block\n\n"))   # the old text, as it was
        self.assertTrue(body.endswith("finding 3"))
        self.assertNotIn("finding 2", body)

    def test_a_crashed_review_is_not_an_accept(self):
        self.assertEqual("", self.revise(["block"], (Outcome("crash"),)))
        self.assertEqual([], self.git)                           # nothing pushed
        self.assertEqual([], self.gh)
        self.assertEqual("lean_stopped", self.ws.events()[-1]["kind"])
        self.assertEqual(1, len(self.mails))


class Prompt(Base):
    def asked(self, **more) -> str:
        with mock.patch.object(lean_judge.review, "codex", return_value=ACCEPT) as call:
            lean_judge.judge(self.ws, "rest-ring", "the spec", "+a line", "/nowhere", **more)
        return call.call_args.args[1]

    def test_a_first_builds_prompt_is_what_it_was(self):
        self.assertEqual(
            "You review one change to this repository, read-only. It should implement the spec below, with "
            "tests. Refuse only for: something the spec's 'Done when' or acceptance tests name that does not "
            "hold, any defect you can name (wrong for some real input or use), a security hole, behaviour "
            "added without tests, or a file the spec does not call for that nothing uses (name it). Accept, "
            "listing findings, only for style, a stated limit or a suggestion, and among those name any "
            "existing function the change should reuse instead of its own, and why; such a finding never "
            "refuses.\n\n"
            f"## Spec\n\nthe spec\n\n## The diff against main\n\n+a line\n\n{NOTED_VERDICT}", self.asked())

    def test_threads_are_cut_to_6000_characters_and_a_shorter_text_is_whole(self):
        self.assertIn("a" * 6000 + "\n\n", self.asked(threads="a" * 6000 + "zzqq"))
        self.assertNotIn("zzqq", self.asked(threads="a" * 6000 + "zzqq"))
        self.assertIn("## The review threads this round answers\n\n" + "b" * 100 + "zzqq\n\n",
                      self.asked(threads="b" * 100 + "zzqq"))


class Nothing(unittest.TestCase):
    def test_no_skipped_event_and_no_switch_turns_the_revise_review_off(self):
        name = "lean_review" + "_skipped"
        found = [str(path) for folder in ("graph", "slicer") for path in (ROOT / folder).rglob("*.py")
                 if name in path.read_text("utf-8")]
        self.assertEqual([], found)
        self.assertEqual(["ws", "repo", "spec_path", "profile", "profile_path", "revise", "pr", "open_questions"],
                         list(inspect.signature(lean_run.run_feature).parameters))
        self.assertEqual(["ws", "feature", "spec", "tree", "built", "command", "round_", "threads"],
                         list(inspect.signature(lean_run.check).parameters))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
