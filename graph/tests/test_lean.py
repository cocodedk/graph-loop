"""The lean loop's entry: its profile, its contact, its end, and its wiring."""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import alert_email
import lean
import lean_run
import providers
import review
import tmp_root  # noqa: F401
from providers import Outcome
from test_keep import repo, sha
from workspace import Workspace
from worktree import Worktree

PROFILE_TEXT = """# Profile: test

## suite_command

    ./run-tests --all

## build_command

    ./build-app

Prose under a heading is not the command.

## artifact

    out/app.bin
"""


class Entry(unittest.TestCase):
    def setUp(self):
        self.repo = repo()
        (pathlib.Path(self.repo) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text(
            "Mechanics are in [profile-test.md](profile-test.md).\n")
        self.ws = Workspace(tempfile.mkdtemp())
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        self.spec.write_text("Restyle the Log screen.\n")
        self.mails = []
        grill = mock.patch.object(lean_run, "grill", return_value="")
        grill.start()
        self.addCleanup(grill.stop)

    def argv(self):
        return ["--workspace", str(self.ws.root), "--repo", self.repo, "--spec", str(self.spec)]

    def test_the_profile_linked_from_claude_md_gives_the_three_values(self):
        path = lean.profile_path(self.repo)
        self.assertEqual(str(pathlib.Path(self.repo) / "profile-test.md"), path)
        self.assertEqual({"suite_command": "./run-tests --all", "build_command": "./build-app",
                          "artifact": "out/app.bin"}, lean.read_profile(path))

    def test_a_profile_missing_a_heading_is_refused_by_name(self):
        path = pathlib.Path(self.repo) / "profile-test.md"
        path.write_text(PROFILE_TEXT.replace("## artifact", "## elsewhere"))
        with self.assertRaisesRegex(SystemExit, "## artifact"):
            lean.read_profile(str(path))

    def test_no_proven_contact_no_run(self):
        with mock.patch.object(lean_run, "run_feature") as feature, \
                self.assertRaisesRegex(SystemExit, "no proven channel"):
            lean.main(self.argv())
        feature.assert_not_called()

    def send(self, body, flags, **kw):
        self.mails.append((kw["subject"], body))

    def finished(self, built: bool):
        """A run whose one feature landed; the build writes the artifact or not."""
        (self.ws.root / "contact").write_text("person@example.test\n")

        def masked(ws, command, cwd):
            if built:
                (pathlib.Path(cwd) / "out").mkdir()
                (pathlib.Path(cwd) / "out" / "app.bin").write_text("app")
            return built, "" if built else "BUILD FAILED"
        with mock.patch.object(lean_run, "run_feature", return_value="abc123") as feature, \
                mock.patch.object(lean_run, "masked", masked), \
                mock.patch.object(alert_email, "send", self.send):
            code = lean.main(self.argv())
        feature.assert_called_once()
        return code

    def test_a_run_that_merged_builds_main_and_says_ready(self):
        self.assertEqual(0, self.finished(built=True))
        (subject, body), = self.mails
        self.assertEqual("graph-loop: ready to accept", subject)
        self.assertIn("- log-screen", body)
        built = next(row for row in self.ws.events() if row["kind"] == "lean_built")
        self.assertTrue(built["passed"])
        self.assertEqual(sha(self.repo, "refs/heads/main"), built["commit"])
        self.assertTrue(pathlib.Path(built["artifact"]).is_file())
        self.assertIn(built["artifact"], body)

    def test_a_red_build_is_never_called_ready(self):
        self.assertEqual(1, self.finished(built=False))
        (subject, body), = self.mails
        self.assertEqual("graph-loop needs you: the build on main", subject)
        self.assertIn("BUILD FAILED", body)

    def test_a_run_that_merged_nothing_builds_nothing(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        with mock.patch.object(lean_run, "run_feature", return_value=""), \
                mock.patch.object(lean_run, "masked") as masked:
            self.assertEqual(1, lean.main(self.argv()))
        masked.assert_not_called()
        self.assertFalse(any(row["kind"] == "lean_built" for row in self.ws.events()))

    def test_a_stopped_feature_stops_the_run(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        argv = self.argv() + ["--spec", str(self.spec)]
        with mock.patch.object(lean_run, "run_feature", return_value="") as feature:
            self.assertEqual(1, lean.main(argv))
        feature.assert_called_once()

    def test_questions_stop_the_run_before_any_build(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        with mock.patch.object(lean_run, "grill", return_value="Which colour?"), \
                mock.patch.object(lean_run, "run_feature") as feature:
            self.assertEqual(2, lean.main(self.argv()))
        feature.assert_not_called()


class Wiring(unittest.TestCase):
    """The real call sites, with only the providers themselves faked."""

    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())
        self.tree = Worktree(repo(), "wiring").create()

    def test_the_builder_works_in_the_tree_with_the_builder_tools_and_no_push(self):
        task = {"id": "wiring", "gate": "./run-tests --all"}
        with mock.patch.object(providers, "claude", return_value=Outcome("ok", cost=0.5)) as call:
            lean_run.build(self.ws, task, "build it", self.tree)
        kw = call.call_args.kwargs
        self.assertEqual(self.tree.path, kw["cwd"])
        self.assertIn("Edit", kw["allowed_tools"])
        self.assertIn("Write", kw["allowed_tools"])
        self.assertIn("Bash(bash ", kw["allowed_tools"])
        self.assertIn("Bash(git push *)", kw["disallowed_tools"])
        paid = next(row for row in self.ws.events() if row["kind"] == "attempt")
        self.assertEqual(("wiring", "build", 0.5), (paid["task"], paid["purpose"], paid["cost"]))

    def test_the_reviewer_reads_the_tree_and_is_asked_for_the_closed_verdict(self):
        with mock.patch.object(review, "codex", return_value=Outcome("ok", verdict="ACCEPT")) as call:
            lean_run.judge(self.ws, "wiring", "the spec", "+a line", self.tree.path)
        self.assertEqual(self.tree.path, call.call_args.kwargs["cwd"])
        prompt = call.call_args.args[1]
        self.assertIn("+a line", prompt)
        self.assertIn('"review":"ACCEPT|REJECT"', prompt)
        self.assertIn("ordinary use", prompt)          # rarer edge cases are findings, not refusals
        self.assertIn("List anything rarer as a finding, and accept.", prompt)

    def test_the_suite_runs_for_real_and_a_red_one_says_why(self):
        passed, tail = lean_run.masked(self.ws, "echo the ring is grey; exit 1", self.tree.path)
        self.assertFalse(passed)
        self.assertIn("the ring is grey", tail)



class Grill(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "a.md"
        self.spec.write_text("Make it blue, and make it red.\n")
        self.mails = []

    def grill(self, answer):
        with mock.patch.object(review, "codex", return_value=answer) as call, \
                mock.patch.object(alert_email, "send", lambda *a, **k: self.mails.append(k)):
            questions = lean_run.grill(self.ws, repo(), [str(self.spec)], "profile.md")
        self.assertIn("Make it blue, and make it red.", call.call_args.args[1])
        return questions

    def test_questions_are_emailed_and_returned(self):
        self.assertEqual("Blue or red?", self.grill(Outcome("ok", verdict="REJECT", text="Blue or red?")))
        self.assertEqual("graph-loop has questions before building", self.mails[0]["subject"])

    def test_clear_specs_ask_nothing(self):
        self.assertEqual("", self.grill(Outcome("ok", verdict="ACCEPT")))
        self.assertEqual([], self.mails)

    def test_a_grill_that_did_not_answer_stops_too(self):
        self.assertIn("did not answer", self.grill(Outcome("malformed")))


if __name__ == "__main__":
    unittest.main()
