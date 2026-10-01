"""After a refusal the grill sees its earlier questions and may ask only what the answers left open or
broke: each answer adds detail, and asking about that new detail is how a spec gets refused forever."""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lean
import lean_git
import lean_run
import lean_spec
import review
import tmp_root  # noqa: F401
from providers import Outcome
from test_keep import repo
from test_lean import PROFILE_TEXT
from workspace import Workspace

EXPECTED_TESTS = 4


class Earlier(unittest.TestCase):
    def setUp(self):
        self.repo = repo()
        (pathlib.Path(self.repo) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("See [profile-test.md](profile-test.md).\n")
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        self.spec.write_text("Restyle the Log screen.\n")
        patched = mock.patch.object(lean_git, "unmerged", return_value=[])
        patched.start()
        self.addCleanup(patched.stop)

    def argv(self):
        return ["--workspace", str(self.ws.root), "--repo", self.repo, "--spec", str(self.spec)]

    def test_a_refusal_keeps_its_questions_in_the_spec(self):
        with mock.patch.object(lean_run, "grill", return_value="Which colour?"):
            self.assertEqual(2, lean.main(self.argv()))
        self.assertEqual("Which colour?", lean_spec.state(self.ws, str(self.spec))["lean_asked"])

    def test_a_long_list_is_kept_whole_and_a_longer_one_ends_with_a_cut_note(self):
        for size, kept in ((3000, 3000), (8000, lean_spec.ASKED_LIMIT)):
            with self.subTest(size=size):
                self.spec.write_text("Restyle the Log screen.\n")
                questions = "".join(f"Question {n} is long?\n" for n in range(size // 20))[:size]
                with mock.patch.object(lean_run, "grill", return_value=questions):
                    self.assertEqual(2, lean.main(self.argv()))
                asked = lean_spec.state(self.ws, str(self.spec))["lean_asked"].rstrip("\n")
                self.assertEqual(questions.rstrip("\n") if size == kept else questions[:kept] + lean_spec.CUT_NOTE, asked)

    def test_the_next_run_hands_them_to_the_grill(self):
        self.spec.write_text("---\nlean_status: questions\nlean_asked: Which colour?\n---\nRestyle.\n")
        with mock.patch.object(lean_run, "grill", return_value="") as grill, \
                mock.patch.object(lean_run, "run_feature", return_value=""):
            lean.main(self.argv())
        self.assertEqual("Which colour?", grill.call_args.kwargs["earlier"])

    def test_the_prompt_narrows_only_when_there_are_earlier_questions(self):
        def prompt(earlier):
            with mock.patch.object(review, "codex", return_value=Outcome("ok", verdict="ACCEPT")) as call:
                lean_run.grill(self.ws, self.repo, [str(self.spec)], "profile.md", earlier=earlier)
            return call.call_args.args[1]
        first, later = prompt(""), prompt("Which colour?")
        self.assertNotIn("Earlier round", first)
        for words in ("Earlier round", "Which colour?", "still leaves unanswered", "never about new detail"):
            self.assertIn(words, later)
        self.assertTrue(later.startswith(first[:200]))                    # the rest of the prompt is the same


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
