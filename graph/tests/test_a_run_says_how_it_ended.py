"""The last line a run prints says how it ended (issue #262).

Started in the background, a run left a log with the mail's one line for every outcome, and the exit
status was lost unless the caller wrapped the process. `lean.main` now ends with `lean: exit <code>, <words>`.
"""

import contextlib
import io
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

EXPECTED_TESTS = 6
URL = "https://example.test/pull/7"


class Ending(unittest.TestCase):
    def go(self, *, unmerged=(), grill=("", "", False), feature=URL, ready=True, fetch=None):
        folder = repo()
        (pathlib.Path(folder) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(folder) / "CLAUDE.md").write_text("See [profile-test.md](profile-test.md).\n")
        ws = Workspace(tempfile.mkdtemp())
        (ws.root / "contact").write_text("person@example.test\n")
        spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        spec.write_text("Restyle the Log screen.\n")
        out = io.StringIO()
        with mock.patch.object(lean_git, "unmerged", return_value=list(unmerged), side_effect=fetch), \
                mock.patch.object(lean_run, "grill", return_value=grill), \
                mock.patch.object(lean_run, "run_feature", return_value=feature), \
                mock.patch.object(lean, "finish", return_value=ready), \
                mock.patch.object(alert_email, "send", lambda *a, **k: None), \
                contextlib.redirect_stdout(out):
            code = lean.main(["--workspace", str(ws.root), "--repo", folder, "--spec", str(spec)])
        return code, out.getvalue().strip().splitlines()[-1]

    def test_a_pull_request_that_is_ready(self):
        self.assertEqual((0, f"lean: exit 0, pr_open {URL}"), self.go())

    def test_a_pull_request_whose_build_is_not_ready(self):
        self.assertEqual((1, f"lean: exit 1, pr_open {URL}, but the build is not ready"), self.go(ready=False))

    def test_a_stopped_feature(self):
        self.assertEqual((1, "lean: exit 1, stopped, see the mail and events.jsonl"), self.go(feature=""))

    def test_questions_for_the_person(self):
        self.assertEqual((2, "lean: exit 2, questions, nothing was built"), self.go(grill=("Which colour?", "", False)))

    def test_unmerged_branches(self):
        self.assertEqual((3, "lean: exit 3, waiting on unmerged branches, nothing was built"),
                         self.go(unmerged=["origin/feat/theirs"]))

    def test_a_fetch_that_failed(self):
        self.assertEqual((1, "lean: exit 1, git fetch failed, nothing was built"),
                         self.go(fetch=RuntimeError("Permission denied")))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())   # the six above and this one


if __name__ == "__main__":
    unittest.main()
