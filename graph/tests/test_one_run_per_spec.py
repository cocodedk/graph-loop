"""Two runs on one spec must not both build it (issue #259).

A second `lean.py` on the same spec ran a second gate on the project's shared compose project and
failed the first one's stack-reset checks. A run now holds a lock on its spec; a second run on that
spec exits at once with an instruction, another spec is unaffected, and the lock is free again once
the run ends.
"""

import fcntl
import os
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


class OneRun(unittest.TestCase):
    def setUp(self):
        self.repo = repo()
        (pathlib.Path(self.repo) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("See [profile-test.md](profile-test.md).\n")
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.folder = pathlib.Path(tempfile.mkdtemp())

    def run_spec(self, name):
        spec = self.folder / f"{name}.md"
        spec.write_text("Restyle the Log screen.\n")
        with mock.patch.object(lean_git, "unmerged", return_value=[]), \
                mock.patch.object(lean_run, "grill", return_value=("", "", False)), \
                mock.patch.object(lean_run, "run_feature", return_value="") as feature, \
                mock.patch.object(alert_email, "send", lambda *a, **k: None):
            code = lean.main(["--workspace", str(self.ws.root), "--repo", self.repo, "--spec", str(spec)])
        return code, feature

    def hold(self, name):
        held = os.open(self.ws.root / f"run-{name}.lock", os.O_WRONLY | os.O_CREAT, 0o644)
        fcntl.flock(held, fcntl.LOCK_EX)
        self.addCleanup(os.close, held)

    def test_a_second_run_on_the_same_spec_exits_at_once_and_builds_nothing(self):
        self.hold("log-screen")
        with mock.patch.object(lean_run, "run_feature") as feature, self.assertRaises(SystemExit) as raised:
            self.run_spec("log-screen")
        self.assertEqual("Another run holds log-screen: wait for it to end, or stop it, then run the spec again.",
                         str(raised.exception))
        feature.assert_not_called()

    def test_another_spec_is_not_held_up(self):
        self.hold("log-screen")
        code, feature = self.run_spec("other-screen")
        self.assertEqual(1, code)           # stopped: the fake feature built nothing, but it was asked
        feature.assert_called_once()

    def test_the_lock_is_free_again_once_the_run_ends(self):
        self.run_spec("log-screen")
        code, feature = self.run_spec("log-screen")
        self.assertEqual(1, code)
        feature.assert_called_once()


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the three above and this one


if __name__ == "__main__":
    unittest.main()
