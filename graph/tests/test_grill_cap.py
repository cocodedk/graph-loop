"""The grill stops blocking after four real refusals; the builder decides what is left and the pull request
says so. Only a real refusal (a REJECT verdict) counts; a grill that failed to answer neither counts nor lets a
build through. The open questions are handed on, not dropped."""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import alert_email
import lean
import lean_body
import lean_git
import lean_run
import lean_spec
import review
import tmp_root  # noqa: F401
from providers import Outcome
from test_keep import repo
from test_lean import PROFILE_TEXT
from test_lean_run import Rig
from workspace import Workspace

EXPECTED_TESTS = 5
REFUSED = Outcome("ok", verdict="REJECT", text="Which colour?")


class Cap(unittest.TestCase):
    def setUp(self):
        self.repo = repo()
        (pathlib.Path(self.repo) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("See [profile-test.md](profile-test.md).\n")
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        self.mails = []
        for patched in (mock.patch.object(lean_git, "unmerged", return_value=[]),
                        mock.patch.object(alert_email, "send", lambda body, flags, **kw: self.mails.append((kw, body)))):
            patched.start()
            self.addCleanup(patched.stop)

    def run_lean(self, rounds, answer, feature=""):
        self.spec.write_text("Restyle the Log screen.\n")
        lean_spec.record(self.ws, str(self.spec), lean_status="questions" if rounds else None,
                         lean_rounds=rounds or None, lean_asked=None)   # where the last run left it
        with mock.patch.object(review, "codex", return_value=answer), \
                mock.patch.object(lean_run, "run_feature", return_value=feature) as run:
            code = lean.main(["--workspace", str(self.ws.root), "--repo", self.repo, "--spec", str(self.spec)])
        return code, run, lean_spec.state(self.ws, str(self.spec))

    def test_a_real_refusal_is_counted_and_a_failure_to_answer_is_not(self):
        code, run, matter = self.run_lean(0, REFUSED)
        self.assertEqual((2, 1), (code, matter["lean_rounds"]))
        run.assert_not_called()
        code, _, matter = self.run_lean(1, Outcome("limit", text="usage limit"))
        self.assertEqual((2, 1), (code, matter["lean_rounds"]))          # not counted, not let through

    def test_the_fourth_real_refusal_goes_on_with_the_open_questions_and_says_so(self):
        _, run, matter = self.run_lean(3, REFUSED)
        run.assert_called_once()
        self.assertEqual("Which colour?", run.call_args.kwargs["open_questions"])
        self.assertEqual(4, matter["lean_rounds"])                            # recorded before it went on
        (kw, body), = self.mails
        self.assertEqual("graph-loop is building with open questions", kw["subject"].partition("] ")[2])
        self.assertIn("No answer is needed to continue", body)
        self.assertNotIn("Nothing was built", body)

    def test_a_failure_to_answer_on_the_last_round_still_stops(self):
        for rounds in (3, 4):                     # also a spec that already stands at the limit
            code, run, matter = self.run_lean(rounds, Outcome("limit", text="usage limit"))
            self.assertEqual((2, rounds), (code, matter["lean_rounds"]))
            run.assert_not_called()


class Handed(unittest.TestCase):
    def test_the_builder_is_asked_to_decide_and_list_its_choices_and_the_pr_shows_them(self):
        base = lean_body.builder_prompt("spec", "gate.sh", "profile.md", "", False)
        prompt = lean_body.builder_prompt("spec", "gate.sh", "profile.md", "", False, "Which colour?")
        self.assertNotIn("left open", base)
        for words in ("left open", "Which colour?", "question, your choice and why", "```"):
            self.assertIn(words, prompt)
        body = lean_body.pr_body("a.md", "", "", "Which colour?", "Colour: blue, because the mock")
        for words in ("Built on the builder's choices", "Jev judged them the builder's to settle", "Which colour?", "Colour: blue, because the mock"):
            self.assertIn(words, body)
        self.assertNotIn("choices", lean_body.pr_body("a.md", "", ""))


class Cleared(Rig):
    def test_publishing_clears_the_count_and_the_questions(self):
        self.spec.write_text("---\nlean_status: questions\nlean_rounds: 4\nlean_asked: Which?\n---\nBody.\n")
        self.run_it(self.builder(("ring.py", "amber\n")))
        matter = lean_spec.state(self.ws, str(self.spec))
        self.assertEqual("pr_open", matter["lean_status"])
        self.assertNotIn("lean_rounds", matter)
        self.assertNotIn("lean_asked", matter)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
