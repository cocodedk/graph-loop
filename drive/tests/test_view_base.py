"""The board's base-branch flag: the loop cuts worktrees from the campaign's
branch, so a base behind this checkout, a failed measure, or a base gone after
a keep is red. Split from `test_view` at the 200-line cap."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_keep import repo
from view_health import base_behind, base_measure, has_kept_commit, recorded_branch

EXPECTED_TESTS = 17


class BaseBehindTest(unittest.TestCase):
    def test_a_base_behind_the_checkout_is_a_red_flag_naming_the_fix(self):
        line = base_behind(161, "campaign/drive")
        self.assertIn("!!", line)
        self.assertIn("161 commits behind", line)
        self.assertIn("git push . HEAD:campaign/drive", line)

    def test_a_base_at_the_checkout_is_no_flag(self):
        self.assertEqual("", base_behind(0, "campaign/drive"))

    def test_a_failed_measure_is_a_flag_not_a_green(self):
        line = base_behind(None, "campaign/drive", error="fatal: bad revision")
        self.assertIn("!! could not measure", line)
        self.assertIn("fatal: bad revision", line)

    def test_a_failed_measure_with_no_words_is_still_a_flag(self):
        self.assertIn("!! could not measure", base_behind(None, "campaign/drive"))

    def test_the_campaigns_recorded_branch_wins_over_the_environment(self):
        rows = [{"kind": "init", "branch": "campaign/other"}, {"kind": "claimed"}]
        self.assertEqual("campaign/other", recorded_branch(rows, "campaign/drive"))
        self.assertEqual("campaign/drive", recorded_branch([{"kind": "init", "branch": ""}], "campaign/drive"))
        self.assertEqual("campaign/drive", recorded_branch([], "campaign/drive"))


class BaseMeasureTest(unittest.TestCase):
    """Every path of the git probe, with a fake runner."""

    # A ref that is missing, one git cannot read and a repository it cannot open
    # are the same exit from `show-ref --verify`, so the measure asks
    # `show-ref --exists` which it was: the scripts below answer that second
    # question too, and only its exit 2 means the branch is not there.
    NOT_THERE = (2, "", "error: reference does not exist")
    ABSENT = (128, "", "fatal: 'refs/heads/campaign/drive' - not a valid ref")

    @staticmethod
    def runner(*answers):
        replies = list(answers)
        return lambda argv: replies.pop(0)

    def test_a_clean_count_is_the_plain_flag(self):
        line = base_measure("campaign/drive", self.runner((0, "abc\n", ""), (0, "3\n", "")))
        self.assertIn("3 commits behind", line)

    def test_a_silent_missing_branch_is_first_use(self):
        self.assertEqual("", base_measure("campaign/drive",
                                          self.runner(self.ABSENT, self.NOT_THERE)))

    def test_only_an_acceptance_with_a_commit_establishes_the_base(self):
        self.assertTrue(has_kept_commit([{"kind": "accepted", "task": "T1", "commit": "abc123"}]))
        self.assertFalse(has_kept_commit([{"kind": "accepted", "task": "T1", "commit": None}]))
        self.assertFalse(has_kept_commit([{"kind": "accepted", "task": "T1"}, {"kind": "claimed"}]))

    def test_a_missing_branch_after_a_keep_is_a_flag(self):
        line = base_measure("campaign/drive", self.runner(self.ABSENT, self.NOT_THERE),
                            established=True)
        self.assertIn("!!", line)
        self.assertIn("GONE", line)

    def test_a_count_that_is_not_a_number_is_a_failed_measure(self):
        for said in ("", "abc", "-1", "3 4"):
            line = base_measure("campaign/drive", self.runner((0, "abc\n", ""), (0, said, "")))
            self.assertIn("could not measure", line, said)

    def test_a_probe_that_fails_with_words_is_a_flag(self):
        broken = (128, "", "fatal: not a git repository")
        line = base_measure("campaign/drive", self.runner(broken, broken))
        self.assertIn("could not measure", line)
        self.assertIn("not a git repository", line)

    def test_a_probe_that_succeeds_with_words_is_a_flag_too(self):
        line = base_measure("campaign/drive", self.runner((0, "abc\n", "warning: refname is ambiguous")))
        self.assertIn("could not measure", line)

    def test_a_failed_count_is_a_flag(self):
        line = base_measure("campaign/drive", self.runner((0, "abc\n", ""), (1, "", "")))
        self.assertIn("could not measure", line)
        self.assertIn("rev-list exited 1", line)


class RealGitTest(unittest.TestCase):
    """Against a real repository, both spellings of what `init` records.

    A campaign records the FULL ref now and an older one records the plain name;
    adding the prefix to a full ref asked about
    `refs/heads/refs/heads/campaign/drive`, which is silently not there — so the
    board called a live branch GONE the moment the campaign kept work on it
    (an independent review).
    """

    def git(self, root: str):
        def run(argv: list[str]) -> tuple[int, str, str]:
            done = subprocess.run(["git", "-C", root, *argv], capture_output=True,
                                  text=True, check=False)
            return done.returncode, done.stdout, done.stderr
        return run

    def test_both_spellings_measure_the_branch_that_is_there(self):
        root = repo()
        subprocess.run(("git", "-C", root, "branch", "campaign/drive", "HEAD"),
                       capture_output=True, check=True)
        for base in ("refs/heads/campaign/drive", "campaign/drive"):
            with self.subTest(base=base):
                self.assertEqual("", base_measure(base, self.git(root), established=True))

    def test_a_tag_of_that_name_does_not_stand_in_for_the_missing_branch(self):
        """`rev-parse` answers with `refs/tags/refs/heads/campaign/drive`, so
        the board measured the tag, counted zero and said nothing — while the
        branch the keeper needs was not there (an independent review)."""
        root = repo()
        subprocess.run(("git", "-C", root, "tag", "refs/heads/campaign/drive", "HEAD"),
                       capture_output=True, check=True)
        line = base_measure("refs/heads/campaign/drive", self.git(root), established=True)
        self.assertIn("GONE", line)
        self.assertEqual("", base_measure("campaign/drive", self.git(root)))   # not yet cut

    def corrupt(self, content: str) -> str:
        """A repository whose campaign branch git cannot read."""
        root = repo()
        subprocess.run(("git", "-C", root, "branch", "campaign/drive", "HEAD"),
                       capture_output=True, check=True)
        (pathlib.Path(root) / ".git/refs/heads/campaign/drive").write_text(content, "utf-8")
        return root

    def test_a_ref_git_cannot_read_is_a_failed_measure_and_never_a_verdict(self):
        """Absent and unreadable are different answers. `rev-parse --git-dir`
        said "the repository is fine" for both, so a corrupt ref read as a
        branch not cut yet — silence before the first keep, a false GONE after
        it (an independent review)."""
        for what, content in (("malformed", "not-a-sha\n"),
                              ("points at no object", "0" * 38 + "42\n")):
            root = self.corrupt(content)
            for established in (False, True):
                with self.subTest(ref=what, established=established):
                    line = base_measure("campaign/drive", self.git(root),
                                        established=established)
                    self.assertIn("could not measure", line)
                    self.assertNotIn("GONE", line)

    def test_a_repository_that_cannot_answer_is_a_failed_measure(self):
        """Not the same thing as a branch that is not there: `show-ref` says
        both with exit 128 and words, so the runner is asked which it was."""
        line = base_measure("campaign/drive", self.git("/nonexistent"), established=True)
        self.assertIn("could not measure", line)
        self.assertNotIn("GONE", line)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
