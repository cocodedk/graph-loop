"""Every error the lean loop shows is a prompt: its cause first, then what to do next.

A reader, a builder asked to repair or the person mailed, gets an instruction it can follow,
not a bare fact. The reasons `check` returns are pinned where their cases are built
(`test_a_profile_may_name_a_lint_command`); these are the ones nothing else pinned.
"""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean
import lean_budget
import lean_run
import tmp_root  # noqa: F401
from providers import Outcome
from test_lean_run import PROFILE, Rig

EXPECTED_TESTS = 7


class Prompts(Rig):
    def test_a_builder_that_did_not_finish_is_told_to_run_the_spec_again(self):
        why, _ = lean_run.check(self.ws, "rest-ring", "spec", mock.Mock(), Outcome("limit", text="resets 2pm"),
                                "run-the-suite", 1)
        self.assertEqual("The builder did not finish (limit). Run the spec again; first read what it said: resets 2pm", why)

    def test_an_empty_change_is_told_what_to_make(self):
        why, _ = lean_run.check(self.ws, "rest-ring", "spec", mock.Mock(diff=lambda **_: " "), Outcome("ok"),
                                "run-the-suite", 1)
        self.assertEqual("Nothing changed. Make the change the spec asks for, then run the suite.", why)

    def test_an_empty_change_carries_what_the_builder_said(self):
        said = Outcome("ok", text="Nothing to do: ring.py already shows the amber ring.")
        why, _ = lean_run.check(self.ws, "rest-ring", "spec", mock.Mock(diff=lambda **_: " "), said,
                                "run-the-suite", 1)
        self.assertEqual("Nothing changed. Make the change the spec asks for, then run the suite. "
                         "The last message was:\nNothing to do: ring.py already shows the amber ring.", why)

    def test_a_card_over_its_budget_is_told_to_reslice_or_speed_up_its_gate(self):
        self.assertEqual("Reslice this card or speed up its gate: it spent $8.01 of its budget of $8, "
                         "so it starts no repair", lean_budget.stopped_words(8.01))

    def test_a_red_build_is_told_to_be_fixed(self):
        sent = []
        tree = mock.Mock(path=tempfile.mkdtemp(), commit="abc")
        with mock.patch.object(lean, "Worktree") as made, \
                mock.patch.object(lean_run, "masked", return_value=(False, "boom")), \
                mock.patch.object(lean_run, "mail", lambda ws, subject, body: sent.append(body)):
            made.return_value.create.return_value = tree
            self.assertFalse(lean.finish(self.ws, self.repo, PROFILE, "rest-ring", "https://example.test/pull/1"))
        self.assertIn("The pull request is open. Fix the red build:\nboom", sent[0])


class Profile(unittest.TestCase):
    def test_a_profile_missing_a_line_is_told_where_to_add_it(self):
        path = pathlib.Path(tempfile.mkdtemp()) / "profile-x.md"
        path.write_text("## suite_command\n\n    run\n")
        with self.assertRaises(SystemExit) as raised:
            lean.read_profile(str(path))
        self.assertEqual(f"Add an indented line under each of these headings in {path}: "
                         "## build_command, ## artifact", str(raised.exception))

    def test_a_repository_that_links_no_profile_is_told_to_link_one(self):
        repo = tempfile.mkdtemp()
        with self.assertRaises(SystemExit) as raised:
            lean.profile_path(repo)
        self.assertEqual(f"Link a profile-*.md from {repo}/CLAUDE.md, or pass --profile: it links none.",
                         str(raised.exception))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the seven above and this one


if __name__ == "__main__":
    unittest.main()
