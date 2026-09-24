"""The lean loop, one feature: build, suite, review, up to two repairs, land or stop.

The builder, the suite, the reviewer and the email are faked; git is real.
"""

import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import alert_email
import lean_run
import tmp_root  # noqa: F401
from providers import Outcome
from test_keep import repo, sha
from workspace import Workspace

PROFILE = {"suite_command": "run-the-suite", "build_command": "build-it", "artifact": "out/app.bin"}
ACCEPT = Outcome("ok", verdict="ACCEPT", text="")


def show(root: str, ref: str, name: str) -> str:
    return subprocess.run(("git", "-C", root, "show", f"{ref}:{name}"), capture_output=True,
                          text=True, check=False).stdout


class Rig(unittest.TestCase):
    def setUp(self):
        self.repo = repo()
        self.base = sha(self.repo)
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "rest ring.md"
        self.spec.write_text("Show the overdue rest ring in amber.\n")
        self.prompts, self.suites, self.reviews, self.mails = [], [], [], []

    def builder(self, *writes):
        """Each call writes the next (name, text) into the worktree."""
        queue = list(writes)

        def build(ws, task, prompt, tree, resume=""):
            self.prompts.append(prompt)
            if queue:
                name, text = queue.pop(0)
                (pathlib.Path(tree.path) / name).write_text(text)
            return Outcome("ok", session="s1")
        return build

    def run_it(self, build, suites=(True,), reviews=(ACCEPT,)):
        suites, reviews = list(suites), list(reviews)

        def masked(ws, command, cwd):
            self.suites.append(command)
            passed = suites.pop(0)
            return passed, "" if passed else "FAILED: AmberTest > overdue"

        def judge(ws, feature, spec, diff, cwd):
            self.reviews.append(diff)
            return reviews.pop(0)
        with mock.patch.object(lean_run, "build", build), \
                mock.patch.object(lean_run, "masked", masked), \
                mock.patch.object(lean_run, "judge", judge), \
                mock.patch.object(alert_email, "send",
                                  lambda body, flags, **kw: self.mails.append((kw, body))):
            return lean_run.run_feature(self.ws, self.repo, str(self.spec), PROFILE, "profile.md")

    def kinds(self):
        return [row["kind"] for row in self.ws.events() if row["kind"].startswith("lean_")]


class GreenFeature(Rig):
    def test_a_green_feature_lands_on_main_and_its_tree_goes(self):
        landed = self.run_it(self.builder(("ring.py", "amber\n")))
        self.assertEqual(landed, sha(self.repo, "refs/heads/main"))
        self.assertEqual("amber\n", show(self.repo, "main", "ring.py"))
        listed = subprocess.run(("git", "-C", self.repo, "ls-tree", "--name-only", "main"),
                                capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(["a.py", "ring.py"], listed)        # the work, and nothing else
        self.assertEqual("amber\n", (pathlib.Path(self.repo) / "ring.py").read_text())  # the checkout moved too
        self.assertEqual(["lean_feature_started", "lean_suite", "lean_review", "lean_merged"], self.kinds())
        started = next(row for row in self.ws.events() if row["kind"] == "lean_feature_started")
        self.assertEqual("rest-ring", started["task"])
        self.assertFalse(pathlib.Path(started["tree"]).exists())
        self.assertIn("ring.py", self.reviews[0])
        self.assertEqual([], self.mails)

    def test_main_held_by_no_checkout_moves_by_a_guarded_update(self):
        subprocess.run(("git", "-C", self.repo, "checkout", "-q", "--detach"), check=True)
        landed = self.run_it(self.builder(("ring.py", "amber\n")))
        self.assertEqual(landed, sha(self.repo, "refs/heads/main"))
        self.assertEqual(self.base, sha(self.repo, "HEAD"))   # the detached checkout was left alone

    def test_main_that_moved_meanwhile_is_merged_not_overwritten(self):
        def build(ws, task, prompt, tree, resume=""):
            (pathlib.Path(tree.path) / "ring.py").write_text("amber\n")
            (pathlib.Path(self.repo) / "other.py").write_text("person\n")
            subprocess.run(("git", "-C", self.repo, "add", "other.py"), check=True)
            subprocess.run(("git", "-C", self.repo, "commit", "-qm", "a person's commit"), check=True)
            return Outcome("ok")
        self.run_it(build)
        self.assertEqual("amber\n", show(self.repo, "main", "ring.py"))
        self.assertEqual("person\n", show(self.repo, "main", "other.py"))
        parents = subprocess.run(("git", "-C", self.repo, "rev-list", "--parents", "-n1", "main"),
                                 capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(3, len(parents))   # a merge commit: itself and two parents

    def test_a_clash_with_what_main_gained_is_never_forced(self):
        def build(ws, task, prompt, tree, resume=""):
            (pathlib.Path(tree.path) / "a.py").write_text("the builder's\n")
            (pathlib.Path(self.repo) / "a.py").write_text("the person's\n")
            subprocess.run(("git", "-C", self.repo, "commit", "-qam", "a person's commit"), check=True)
            return Outcome("ok")
        landed = self.run_it(build)
        person = sha(self.repo, "refs/heads/main")
        self.assertEqual("", landed)
        self.assertEqual("the person's\n", show(self.repo, person, "a.py"))
        self.assertEqual("the person's\n", (pathlib.Path(self.repo) / "a.py").read_text())
        stopped = next(row for row in self.ws.events() if row["kind"] == "lean_stopped")
        self.assertIn("could not land", stopped["why"])
        self.assertIn("could not land", self.mails[0][1])
        self.assertEqual("the builder's\n", (pathlib.Path(stopped["tree"]) / "a.py").read_text())


class Repair(Rig):
    def test_a_red_suite_gets_one_repair_with_the_failure_text(self):
        landed = self.run_it(self.builder(("ring.py", "grey\n"), ("ring.py", "amber\n")),
                             suites=(False, True))
        self.assertTrue(landed)
        self.assertEqual(2, len(self.prompts))
        self.assertIn("FAILED: AmberTest > overdue", self.prompts[1])
        self.assertEqual(["lean_feature_started", "lean_suite", "lean_repair", "lean_suite",
                          "lean_review", "lean_merged"], self.kinds())

    def test_a_refused_review_gets_one_repair_with_its_findings(self):
        refused = Outcome("ok", verdict="REJECT", text="no test covers the amber colour")
        self.run_it(self.builder(("ring.py", "amber\n"), ("ring_test.py", "test\n")),
                    suites=(True, True), reviews=(refused, ACCEPT))
        self.assertIn("no test covers the amber colour", self.prompts[1])
        self.assertEqual("test\n", show(self.repo, "main", "ring_test.py"))

    def test_still_failing_after_the_repair_stops_emails_and_keeps_the_work(self):
        landed = self.run_it(self.builder(("ring.py", "grey\n"), ("ring.py", "grey1\n"),
                                          ("ring.py", "grey2\n")),
                             suites=(False, False, False))
        self.assertEqual("", landed)
        self.assertEqual(self.base, sha(self.repo, "refs/heads/main"))
        self.assertEqual(1 + lean_run.REPAIRS, len(self.prompts))   # never another build
        self.assertEqual("lean_stopped", self.kinds()[-1])
        (sent, body), = self.mails
        self.assertEqual("graph-loop needs you: rest-ring", sent["subject"])
        self.assertEqual("person@example.test", sent["recipient"])
        self.assertIn("FAILED: AmberTest > overdue", body)
        stopped = next(row for row in self.ws.events() if row["kind"] == "lean_stopped")
        self.assertEqual("grey2\n", (pathlib.Path(stopped["tree"]) / "ring.py").read_text())

    def test_a_second_refusal_gets_the_second_repair(self):
        refused = Outcome("ok", verdict="REJECT", text="a new finding")
        landed = self.run_it(self.builder(("ring.py", "a\n"), ("ring.py", "b\n"), ("ring.py", "c\n")),
                             suites=(True, True, True), reviews=(refused, refused, ACCEPT))
        self.assertTrue(landed)
        self.assertEqual(3, len(self.prompts))
        self.assertEqual("c\n", show(self.repo, "main", "ring.py"))

    def test_a_builder_that_changes_nothing_is_not_reviewed(self):
        self.run_it(self.builder(), suites=(), reviews=())
        self.assertEqual([], self.suites)
        self.assertIn("changed nothing", self.mails[0][1])


if __name__ == "__main__":
    unittest.main()
