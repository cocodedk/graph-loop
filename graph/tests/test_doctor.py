"""The self-check: every complaint here is a mistake we actually made.

Written after a person had to notice each of them. While nobody is watching, the
loop asks itself these questions every round.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import yaml  # type: ignore[import-untyped]  # no stubs in this environment

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from backlog import Backlog
from doctor import (
    check_backlog,
    check_campaign,
)
from workspace import Workspace

EXPECTED_TESTS = 22
REPO = "/srv/example-repo"  # a checkout path, independent of the launch directory


def book(**changes) -> Backlog:
    row = {"id": "T1", "goal": "do the thing", "status": "todo", "needs": [],
           "files": ["simulation/a.py"], "gate": "cd simulation && python3 -m unittest a",
           "done_when": "a passes"}
    row.update(changes)
    path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": [row]},
                                   sort_keys=False))
    return Backlog(path)


def space() -> Workspace:
    return Workspace(tempfile.mkdtemp()).init(goal="pilot", backlog="b.yaml")


class BacklogTest(unittest.TestCase):
    def test_a_gate_with_an_absolute_path_is_named(self):
        out = check_backlog(book(gate=f"cd {REPO}/simulation && python3 -m unittest a"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_gate_naming_another_checkout_is_named_too(self):
        # the check knew only ITS OWN repo path, so a gate reaching into a
        # different checkout passed — and the test passed by accident
        out = check_backlog(book(gate="cd /srv/other-checkout/simulation && python3 -m unittest a"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_system_path_is_not_a_checkout(self):
        out = check_backlog(book(gate="python3 -m unittest a 2>/dev/null"))
        self.assertEqual([], [one for one in out if "absolute path" in one.what])

    def test_a_worktree_under_tmp_is_still_a_checkout(self):
        out = check_backlog(book(gate="cd /tmp/graph-abc/task-T1 && python3 -m unittest a"))
        self.assertEqual(1, len(out))
        self.assertIn("absolute path", out[0].what)

    def test_a_file_the_gate_creates_is_its_own_scratch(self):
        # the T10 gates write /tmp/t10-*.txt and read it back: scratch, not a checkout
        out = check_backlog(book(
            gate="python3 -m unittest a > /tmp/t10-test_bundle.txt\n"
                 "grep -q OK /tmp/t10-test_bundle.txt"))
        self.assertEqual([], [one for one in out if "absolute path" in one.what])

    def test_a_file_the_gate_tees_is_scratch_too(self):
        # the nine T10 gates create theirs with `tee`, not a redirect
        out = check_backlog(book(
            gate="python3 -m unittest a 2>&1 | tee /tmp/t10-x.txt | grep -q OK\n"
                 "grep -q '^Ran 201' /tmp/t10-x.txt"))
        self.assertEqual([], [one for one in out if "absolute path" in one.what])

    def test_a_sed_fragment_is_not_a_path(self):
        # T4.close's gate carries `s/.../\\1/p`: one segment, not a checkout
        out = check_backlog(book(
            gate="curl -sf localhost/health | sed -n 's/.*\"run\":\"\\([^\"]*\\)\".*/\\1/p'"))
        self.assertEqual([], [one for one in out if "absolute path" in one.what])

    def test_a_tmp_directory_it_never_created_is_a_checkout(self):
        out = check_backlog(book(gate="cd /tmp/other-checkout && python3 -m unittest a"))
        self.assertEqual(1, len(out))

    def test_an_awk_pattern_and_a_url_are_not_paths(self):
        out = check_backlog(book(
            gate="curl -sf http://build-host:8000/health | awk '/^OK/{ok=1} END{exit !ok}'"))
        self.assertEqual([], [one for one in out if "absolute path" in one.what])

    def test_a_task_with_no_gate_is_named(self):
        out = check_backlog(book(gate=""))
        self.assertIn("no gate", out[0].what)

    def test_a_builder_that_may_edit_its_own_judge_is_named(self):
        out = check_backlog(book(files=["tests/test_a.py"],
                                 gate="python3 -m unittest test_a"))
        self.assertIn("may edit the test", out[0].what)

    def test_unless_writing_that_test_is_the_work(self):
        self.assertEqual([], check_backlog(book(files=["tests/test_a.py"],
                                                gate="python3 -m unittest test_a",
                                                gate_files_are_the_work=True)))

    def test_a_task_claiming_a_suite_its_gate_never_runs_is_named(self):
        out = check_backlog(book(done_when="the whole suite is green",
                                 gate="python3 -m unittest a"))
        self.assertIn("whole suite", out[0].what)

    def test_a_healthy_task_draws_no_complaint(self):
        self.assertEqual([], check_backlog(book()))


class CampaignTest(unittest.TestCase):
    def test_a_stop_flag_is_named_because_nothing_will_run(self):
        here = space()
        here.stop()
        self.assertIn("stop flag", check_campaign(here)[0].what)

    def test_a_lock_held_by_a_dead_process_is_named(self):
        # The lock lives with the stack, not with this campaign, and no
        # environment moves it — so a test stands in for where it lives, or it
        # writes over the record of a driver running on this host.
        import unittest.mock
        here, folder = space(), tempfile.mkdtemp()
        self.enterContext(unittest.mock.patch("worktree_lock.shared", return_value=folder))
        (pathlib.Path(folder) / "live-stack.lock").write_text("T2 999999")
        self.assertTrue(any("lock" in row.what for row in check_campaign(here)))


class ClaimAgeTest(unittest.TestCase):
    def test_a_fresh_claim_is_healthy_and_draws_no_complaint(self):
        import os
        here = space()
        here.claim("T1", pgid=os.getpgid(0), account="work", worktree="/tmp/x")
        self.assertEqual([], [c for c in check_campaign(here) if c.about == "T1"])


class SuiteClaimTest(unittest.TestCase):
    def test_a_committed_gate_script_is_not_a_one_test_gate(self):
        loud = book(done_when="the whole suite passes", gate="python3 -m unittest one")
        self.assertTrue(any("whole suite" in c.what for c in check_backlog(loud)))
        quiet = book(done_when="the whole suite passes", gate="bash packages/27/gate.sh")
        self.assertEqual([], [c for c in check_backlog(quiet) if "whole suite" in c.what])

    def test_a_multiline_gate_with_no_ampersand_still_proves_the_suite(self):
        # triage-no-mutation's shape: `set -e -o pipefail`, one check per
        # line, no `&&` and no `run_all` to say it is more than one step
        gate = ("set -e -o pipefail\n"
                "cd simulation\n"
                "python3 -m unittest -v test_no_mutation 2>&1 | tee /tmp/out.txt\n"
                "grep -q 'Ran 2 tests' /tmp/out.txt\n")
        out = check_backlog(book(done_when="the suite is green", gate=gate))
        self.assertEqual([], [c for c in out if "whole suite" in c.what])

    def test_a_multiline_gate_without_pipefail_still_complains(self):
        # no `set -e -o pipefail`: an earlier failing line could still hide
        # behind a later passing one, so the extra lines prove nothing
        gate = ("cd simulation\n"
                "python3 -m unittest -v test_no_mutation 2>&1 | tee /tmp/out.txt\n"
                "grep -q 'Ran 2 tests' /tmp/out.txt\n")
        out = check_backlog(book(done_when="the suite is green", gate=gate))
        self.assertTrue(any("whole suite" in c.what for c in out))

    def test_a_header_plus_one_test_line_is_still_one_test(self):
        # the header itself is not a check: `set -e -o pipefail` plus a
        # single unittest line still proves only one test, header included
        gate = "set -e -o pipefail\npython3 -m unittest -v test_no_mutation\n"
        out = check_backlog(book(done_when="the suite is green", gate=gate))
        self.assertTrue(any("whole suite" in c.what for c in out))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
