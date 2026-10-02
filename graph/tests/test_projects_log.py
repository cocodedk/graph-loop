"""A start of lean.py records its repository's folder in `graph-loop/projects` of the state folder, so the
dashboard can list the project after the loop has exited (docs/lean/08-awaiting-you.md)."""

import os
import pathlib
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean
import lean_git
import lean_run
import loops_projects
import projects_log
import tmp_root  # noqa: F401
from test_keep import repo
from test_lean import PROFILE_TEXT
from workspace import Workspace

EXPECTED_TESTS = 9


class Recorded(unittest.TestCase):
    def setUp(self):
        self.state = pathlib.Path(tempfile.mkdtemp()) / "state"      # missing: the run creates it
        self.file = self.state / "graph-loop" / "projects"
        patched = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.state)})
        patched.start()
        self.addCleanup(patched.stop)
        self.repo = repo()
        (pathlib.Path(self.repo) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("Mechanics are in [profile-test.md](profile-test.md).\n")
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        self.spec.write_text("Restyle the Log screen.\n")
        patched = mock.patch.object(lean_git, "unmerged", return_value=[])
        patched.start()
        self.addCleanup(patched.stop)

    def start(self):
        argv = ["--workspace", str(self.ws.root), "--repo", self.repo, "--spec", str(self.spec)]
        with mock.patch.object(lean_run, "grill", return_value=("Which colour?", "", False)):
            return lean.main(argv)

    def test_a_start_writes_the_repos_absolute_folder_and_makes_the_missing_state_folder(self):
        self.assertEqual(2, self.start())
        self.assertEqual([os.path.realpath(self.repo)], self.file.read_text().splitlines())

    def test_a_second_start_adds_nothing(self):
        self.start()
        self.start()
        self.assertEqual([os.path.realpath(self.repo)], self.file.read_text().splitlines())

    def test_the_other_lines_stay_as_they_are_in_their_order(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text("/b/one\n/a/two")            # no final newline
        self.start()
        self.assertEqual(["/b/one", "/a/two", os.path.realpath(self.repo)], self.file.read_text().splitlines())

    def test_a_folder_already_on_a_line_is_not_added_again(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text(f"/b/one\n{os.path.realpath(self.repo)}\n/a/two\n")
        self.start()
        self.assertEqual(3, len(self.file.read_text().splitlines()))

    def test_a_file_that_cannot_be_written_does_not_stop_the_run(self):
        self.state.parent.mkdir(exist_ok=True)
        self.state.write_text("a file where the state folder should be")
        self.assertEqual(2, self.start())

    def test_an_unset_or_empty_state_folder_means_the_local_state_folder_of_the_home(self):
        for value in (None, ""):
            with self.subTest(value=value):
                env = {"HOME": "/h"} if value is None else {"HOME": "/h", "XDG_STATE_HOME": value}
                with mock.patch.dict(os.environ, env, clear=True):
                    self.assertEqual(pathlib.Path("/h/.local/state/graph-loop/projects"), loops_projects.path())

    def test_reading_gives_the_folders_in_file_order_and_nothing_for_a_missing_file(self):
        self.assertEqual([], loops_projects.folders())
        self.file.parent.mkdir(parents=True)
        self.file.write_text("/b\n\n/a \n")
        self.assertEqual(["/b", "/a "], loops_projects.folders())   # a trailing space is part of the name

    def test_a_folder_is_recorded_as_it_resolves_symlinks_before_dots(self):
        base = pathlib.Path(tempfile.mkdtemp())
        (base / "real" / "inner").mkdir(parents=True)
        (base / "other").mkdir()
        (base / "link").symlink_to(base / "real" / "inner")
        spelled = f"{base}/link/../../other"      # the link leads into real/inner, so `..` twice is base
        self.assertNotEqual(os.path.normpath(spelled), str(os.path.realpath(base / "other")))   # a lexical `..` differs
        projects_log.record(spelled)
        self.assertEqual([os.path.realpath(base / "other")], loops_projects.folders())

    def test_starts_at_once_record_a_folder_once(self):
        with ThreadPoolExecutor(16) as pool:
            list(pool.map(projects_log.record, [self.repo] * 64))
        self.assertEqual([os.path.realpath(self.repo)], loops_projects.folders())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
