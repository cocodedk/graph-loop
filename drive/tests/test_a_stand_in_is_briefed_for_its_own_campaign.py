"""The stand-in is briefed for the campaign that started it, never another's.

STAND-IN.md named `campaign/drive` and `scratchpad/drive-campaigns/current` in
its own text, so a handoff for campaign B handed its stand-in campaign A's
commands: merge and push A's branch, restart A's driver (astra round 4,
finding 14). The brief is rendered per launch — `{{CAMPAIGN}}` and `{{BRANCH}}`
filled from THIS campaign's own record — and the session runs with
DRIVE_CAMPAIGN and DRIVE_BRANCH set, so every tool the stand-in runs (the Stop
hook that beats for it included) resolves the same campaign. The branch is read
through `campaign_of.branch_of`, the one function the driver builds its keeper
with, so the stand-in and its driver can never name different branches.

The rig is test_handoff_owns_what_it_kills.py's, the front door for a handoff
run against a fake tmux.
"""

from __future__ import annotations

import pathlib
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from test_handoff_owns_what_it_kills import HandoffRig
from test_handoff_two_campaigns import FAKE

EXPECTED_TESTS = 4

# the same fake tmux, but it keeps the brief that was loaded into the buffer
KEEPS_BRIEF = FAKE.replace(
    "  load-buffer|paste-buffer|send-keys) : ;;\n",
    '  load-buffer)  cat "${@: -1}" > "$FAKE_TMUX_STATE/brief" ;;\n'
    "  paste-buffer|send-keys) : ;;\n")


class BriefTest(HandoffRig):
    def setUp(self):
        HandoffRig.setUp(self)
        self.tmux(KEEPS_BRIEF)

    def test_the_brief_names_this_campaigns_branch_and_directory(self):
        self.assertIn("started", self.handoff(DRIVE_BRANCH="campaign/other").stdout)
        brief = (self.state / "brief").read_text("utf-8")
        self.assertIn("git merge campaign/other", brief)
        self.assertIn(f"{self.camp}/restart.flag", brief)
        self.assertNotIn("campaign/drive", brief)
        self.assertNotIn("drive-campaigns/current", brief)

    def test_the_session_runs_with_its_own_campaign_and_branch_set(self):
        self.handoff(DRIVE_BRANCH="campaign/other")
        started = (self.state / self.session).read_text("utf-8")
        self.assertIn(f"DRIVE_CAMPAIGN='{self.camp}'", started)
        self.assertIn("DRIVE_BRANCH='campaign/other'", started)

    def test_a_campaign_whose_init_recorded_no_branch_gets_its_drivers(self):
        """One reading, the driver's (`campaign_of.branch_of`): a campaign
        started before `init` recorded branches keeps its stand-in, briefed
        with the branch its own driver and keeper use. Refusing it instead
        gave the loop a second answer for one campaign — and no stand-in."""
        (self.camp / "events.jsonl").write_text('{"kind": "init", "branch": ""}\n', "utf-8")
        self.assertIn("started", self.handoff(DRIVE_BRANCH="").stdout)
        self.assertIn("git merge campaign/drive", (self.state / "brief").read_text("utf-8"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
