"""A plan sees earlier campaign work regardless of the repository checkout."""

import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import tmp_root  # noqa: F401 — isolate every temporary repository

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import intelligence
from contracts import validate
from git_fixture import commit, git
from keep import Keeper
from workspace import Workspace

import slicer


class CampaignTip(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.source = self.repo / "spec.md"
        self.source.write_text("Feedback is delivered.\n")
        commit(self.repo)
        git(self.repo, "checkout", "-qb", "campaign/feedback")
        (self.repo / "contracts").mkdir()
        (self.repo / "contracts" / "Feedback.kt").write_text("interface Feedback {}\n")
        commit(self.repo)
        git(self.repo, "checkout", "-q", "main")
        self.tip = Keeper(str(self.repo), "campaign/feedback").tip()
        self.backlog = self.root / "backlog"
        self.backlog.mkdir()

    def answer(self, **changes):
        made = {"name": "feedback", "source": ["spec.md:1"], "goal": "deliver feedback",
                "why": "feedback is missing", "needs": [], "atoms": [],
                "files": ["contracts/Feedback.kt"],
                "uses": ["contracts/Feedback.kt:interface Feedback"],
                "gate": "set -e -o pipefail\nfalse", "done_when": "feedback arrives"}
        return {"result": "MOLECULE", "reason": "missing behavior", "molecule": {**made, **changes}}

    def check(self, **changes):
        return validate(self.answer(**changes), repo=self.repo, sources=[self.source],
                        rows=[], tip=self.tip)

    def test_a_file_and_name_only_on_the_campaign_branch_validate(self):
        self.assertFalse((self.repo / "contracts" / "Feedback.kt").exists())
        self.assertEqual("MOLECULE", self.check()["result"])

    def test_a_name_that_exists_nowhere_is_refused(self):
        with self.assertRaisesRegex(ValueError, "unavailable name.*Missing"):
            self.check(uses=["contracts/Feedback.kt:interface Missing"])

    def test_a_file_that_exists_nowhere_still_needs_permission_to_be_created(self):
        with self.assertRaisesRegex(ValueError, "may_add_files.*Missing.kt"):
            self.check(files=["contracts/Missing.kt"])

    def test_changing_the_working_branch_does_not_change_validation(self):
        for branch in ("main", "campaign/feedback"):
            git(self.repo, "checkout", "-q", branch)
            self.assertEqual("MOLECULE", self.check()["result"])
        (self.repo / "contracts" / "Feedback.kt").write_text("interface Unrelated {}\n")
        self.assertEqual("MOLECULE", self.check()["result"])

    def test_names_and_files_only_in_the_checkout_do_not_count(self):
        (self.repo / "local.kt").write_text("interface Local {}\n")
        commit(self.repo)  # committed to main, absent from the campaign
        with self.assertRaisesRegex(ValueError, "unavailable name.*Local"):
            self.check(uses=["local.kt:interface Local"])
        with self.assertRaisesRegex(ValueError, "may_add_files.*local.kt"):
            self.check(files=["local.kt"])

    def test_answer_and_checker_revalidation_use_the_same_tip(self):
        checker = lambda made: SimpleNamespace(molecule={**made, "note": "checked"}, findings=[])
        self.assertEqual(("published", "feedback"), slicer.run_answer(
            json.dumps(self.answer()), repo=self.repo, backlog=self.backlog,
            sources=[self.source], tip=self.tip, checker=checker))

    def main(self, *args):
        answer = self.root / "answer.json"
        answer.write_text(json.dumps(self.answer()))
        with mock.patch.object(slicer, "ask") as planner, \
                mock.patch.object(slicer, "make_checker", return_value=None), \
                mock.patch.object(intelligence, "CAMPAIGN", None):
            code = slicer.main(["--repo", str(self.repo), "--backlog", str(self.backlog),
                                "--source", "spec.md", "--answer", str(answer), *args])
        planner.assert_not_called()
        return code

    def test_the_cli_passes_the_campaign_commit_to_validation(self):
        self.assertEqual(0, self.main("--tip", self.tip))

    def test_the_cli_uses_the_workspaces_branch_when_no_tip_is_given(self):
        space = Workspace(self.root / "campaign").init(
            goal="feedback", backlog=str(self.backlog), branch="refs/heads/campaign/feedback")
        # A same-named tag points to main: only the workspace's branch counts.
        git(self.repo, "tag", "campaign/feedback", "main")
        self.assertEqual(0, self.main("--campaign", str(space.root)))


if __name__ == "__main__":
    unittest.main()
