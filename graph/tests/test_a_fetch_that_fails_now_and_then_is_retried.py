"""A `git fetch` that fails now and then must not lose the run (issue #256).

Over SSH the fetch failed about one try in five to ten with a key that was valid; the next try
worked. `lean_git.unmerged` retries it, and when every try fails the run stops with an instruction
and git's own message, not a traceback.
"""

import pathlib
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
import tmp_root  # noqa: F401
from test_keep import repo
from test_lean import PROFILE_TEXT
from workspace import Workspace

EXPECTED_TESTS = 3
DENIED = "git fetch --quiet --prune: Permission denied (publickey)."


def flaky(failures):
    calls = []

    def git(cwd, *args, **_kw):
        calls.append(args[0])
        if args[0] == "fetch" and calls.count("fetch") <= failures:
            raise RuntimeError(DENIED)
        return "origin/lean/theirs"
    return git, calls


class Retry(unittest.TestCase):
    def test_a_fetch_that_fails_twice_and_then_works_is_retried(self):
        git, calls = flaky(2)
        with mock.patch.object(lean_git, "git", git), mock.patch.object(lean_git.time, "sleep") as sleep:
            self.assertEqual(["origin/lean/theirs"], lean_git.unmerged("repo"))
        self.assertEqual(3, calls.count("fetch"))
        self.assertEqual(2, sleep.call_count)

    def test_a_fetch_that_always_fails_is_tried_three_times_and_then_raises(self):
        git, calls = flaky(99)
        with mock.patch.object(lean_git, "git", git), mock.patch.object(lean_git.time, "sleep"), \
                self.assertRaises(RuntimeError) as raised:
            lean_git.unmerged("repo")
        self.assertEqual(3, calls.count("fetch"))
        self.assertIn("Permission denied", str(raised.exception))


class Stop(unittest.TestCase):
    def test_an_exhausted_fetch_stops_the_run_with_an_instruction(self):
        folder = repo()
        (pathlib.Path(folder) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(folder) / "CLAUDE.md").write_text("Mechanics are in [profile-test.md](profile-test.md).\n")
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        spec.write_text("Restyle the Log screen.\n")
        mails = []
        with mock.patch.object(lean_git, "unmerged", side_effect=RuntimeError(DENIED)), \
                mock.patch.object(lean_run, "run_feature") as feature, \
                mock.patch.object(alert_email, "send", lambda body, flags, **kw: mails.append((kw["subject"], body))):
            self.assertEqual(1, lean.main(["--workspace", str(self.ws.root), "--repo", folder, "--spec", str(spec)]))
        feature.assert_not_called()
        (subject, body), = mails
        self.assertEqual("graph-loop needs you: git fetch failed", subject.partition("] ")[2])
        self.assertIn(f"Run the spec again once `git fetch origin` works in {folder}. Nothing was built.", body)
        self.assertIn(DENIED, body)
        self.assertIn("lean_fetch_failed", [row["kind"] for row in self.ws.events()])


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the three above and this one


if __name__ == "__main__":
    unittest.main()
