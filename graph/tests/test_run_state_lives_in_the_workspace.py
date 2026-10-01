"""A run's state is kept in the workspace, never written into the spec file (issue #257).

The state (`lean_status`, `lean_pr`, `lean_worktree`, `lean_rounds`, `lean_asked`) lived in the spec's
front matter in the main checkout: `git add -A` committed it by accident, `git pull` aborted on it, and
removing it to commit a clean edit lost the resume point. It is now `<workspace>/spec-<name>.json`.
A spec an older run marked in its front matter is still read, and the workspace's word wins.
"""

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_spec
from test_lean_run import Rig

EXPECTED_TESTS = 5
OLDER = "---\nlean_status: stopped\nlean_worktree: /somewhere/kept\nlean_rounds: 2\n---\nShow the ring.\n"


class State(Rig):
    def kept(self):
        return json.loads((self.ws.root / "spec-rest-ring.json").read_text())

    def test_a_published_run_leaves_the_spec_file_untouched(self):
        before = self.spec.read_bytes()
        url = self.run_it(self.builder(("ring.py", "amber\n")))
        self.assertEqual(before, self.spec.read_bytes())
        self.assertEqual(("pr_open", url), (self.kept()["lean_status"], self.kept()["lean_pr"]))

    def test_a_stopped_run_leaves_the_spec_untouched_and_the_next_run_resumes_its_tree(self):
        before = self.spec.read_bytes()
        self.assertEqual("", self.run_it(self.builder(), suites=(), reviews=()))
        self.assertEqual(before, self.spec.read_bytes())
        kept = lean_spec.state(self.ws, str(self.spec))
        self.assertEqual("stopped", kept["lean_status"])
        self.run_it(self.builder(), suites=(), reviews=())
        started = [row for row in self.ws.events() if row["kind"] == "lean_feature_started"]
        self.assertEqual([False, True], [row["resumed"] for row in started])


class Reading(Rig):
    def test_a_spec_an_older_run_marked_in_its_front_matter_is_still_read(self):
        self.spec.write_text(OLDER)
        self.assertEqual({"lean_status": "stopped", "lean_worktree": "/somewhere/kept", "lean_rounds": 2},
                         lean_spec.state(self.ws, str(self.spec)))

    def test_the_workspaces_word_wins_and_a_cleared_field_stays_cleared(self):
        self.spec.write_text(OLDER)
        lean_spec.record(self.ws, str(self.spec), lean_status="pr_open", lean_worktree=None)
        self.assertEqual({"lean_status": "pr_open", "lean_rounds": 2}, lean_spec.state(self.ws, str(self.spec)))
        self.assertEqual(OLDER, self.spec.read_text())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())   # the four above and this one


if __name__ == "__main__":
    unittest.main()
