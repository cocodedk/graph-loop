"""The lean loop's entry: its profile, its contact, its end, and its wiring."""

import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import alert_email
import lean
import lean_git
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
        for name, fake in ((lean_run, "grill"), (lean_git, "unmerged")):
            patched = mock.patch.object(name, fake, return_value=[] if fake == "unmerged" else "")
            patched.start()
            self.addCleanup(patched.stop)

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
        subprocess.run(("git", "-C", self.repo, "branch", "lean/log-screen"), check=True)
        with mock.patch.object(lean_run, "run_feature", return_value="https://example.test/pull/7") as feature, \
                mock.patch.object(lean_run, "masked", masked), \
                mock.patch.object(alert_email, "send", self.send):
            code = lean.main(self.argv())
        feature.assert_called_once()
        return code

    def test_a_published_feature_builds_its_branch_and_says_ready(self):
        self.assertEqual(0, self.finished(built=True))
        (subject, body), = self.mails
        self.assertEqual("graph-loop: ready for review", subject.partition("] ")[2])
        self.assertIn("log-screen: https://example.test/pull/7", body)
        built = next(row for row in self.ws.events() if row["kind"] == "lean_built")
        self.assertTrue(built["passed"])
        self.assertEqual(sha(self.repo, "refs/heads/lean/log-screen"), built["commit"])
        self.assertTrue(pathlib.Path(built["artifact"]).is_file())
        self.assertIn(built["artifact"], body)

    def test_a_red_build_is_never_called_ready(self):
        self.assertEqual(1, self.finished(built=False))
        (subject, body), = self.mails
        self.assertEqual("graph-loop needs you: the build of log-screen", subject.partition("] ")[2])
        self.assertIn("BUILD FAILED", body)

    def test_a_run_that_merged_nothing_builds_nothing(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        with mock.patch.object(lean_run, "run_feature", return_value=""), \
                mock.patch.object(lean_run, "masked") as masked:
            self.assertEqual(1, lean.main(self.argv()))
        masked.assert_not_called()
        self.assertFalse(any(row["kind"] == "lean_built" for row in self.ws.events()))

    def test_one_spec_per_run(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        argv = self.argv() + ["--spec", str(self.spec)]
        with mock.patch.object(lean_run, "run_feature") as feature, \
                self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            lean.main(argv)
        feature.assert_not_called()

    def test_an_unmerged_branch_stops_the_run_before_the_grill(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        with mock.patch.object(lean_git, "unmerged", return_value=["origin/feat/theirs"]), \
                mock.patch.object(lean_run, "grill") as grill, \
                mock.patch.object(lean_run, "run_feature") as feature, \
                mock.patch.object(alert_email, "send", self.send):
            self.assertEqual(3, lean.main(self.argv()))
        grill.assert_not_called()
        feature.assert_not_called()
        (subject, body), = self.mails
        self.assertEqual("graph-loop is waiting: unmerged branches", subject.partition("] ")[2])
        self.assertIn("- origin/feat/theirs", body)

    def test_no_profile_emails_the_ones_to_choose_from(self):
        (self.ws.root / "contact").write_text("person@example.test\n")
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("No profile here.\n")
        with mock.patch.object(alert_email, "send", lambda *a, **k: self.mails.append((a, k))), \
                self.assertRaises(SystemExit):
            lean.main(self.argv())
        (body, _flags), sent = self.mails[0]
        self.assertEqual("graph-loop needs a profile", sent["subject"].partition("] ")[2])
        self.assertIn("web-node.md", body)

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



if __name__ == "__main__":
    unittest.main()
