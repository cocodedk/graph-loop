"""A stall opens with the reason from the step that ended it."""

import json
import unittest

from gate_reports import HEADING
from lanes import run_lanes
from providers import Outcome
from test_loop import Fakes, loop_for, task
from turn import stood_down


class StallReasonsTest(unittest.TestCase):
    def draft(self, space):
        stood_down(space, 78, "nothing startable")
        body = next((space.root / "issues").glob("*.md")).read_text()
        return body, "\n".join(body.splitlines()[:20])

    def test_contract_draft_opens_with_verdict_and_omits_reviewed_source(self):
        reason = "The gate accepts a constant return without measuring the input."
        source = "kotlinOptions { jvmTarget = 17 }\n10: pop\n11: aload_0\n12: areturn"
        mixed = reason + "\n\n```kotlin\n" + source + "\n```"
        fakes = Fakes(review=[Outcome("ok", verdict="REJECT", text=mixed,
                                     raw="Reviewed context:\n" + source * 100)])
        loop, book, space = loop_for(task(replans=1, replan_history=[reason]), fakes)
        loop.run_task(book.task("T1"))
        body, opening = self.draft(space)
        self.assertIn(reason, opening)
        self.assertIn("Loop step: contract", opening)
        self.assertNotIn("jvmTarget", body)
        self.assertNotIn("aload_0", body)
        self.assertEqual(reason, book.task("T1")["refused_why"])
        self.assertIn("the same complaint twice", space.alerts(unread_only=False)[0])

    def test_old_mixed_records_prefer_the_short_verdict_field(self):
        _, book, space = loop_for(task(status="refused_contract"), Fakes())
        reason = "The empty-input branch bypasses the required validation."
        book.note("T1", refused_why="A whole reviewed contract prompt\n\n" + "wrong context" * 100)
        space.artifact("T1", "contract-answer", "A whole reviewed contract prompt" * 100)
        space.event("refused", task="T1", step="contract", why=reason)
        body, opening = self.draft(space)
        self.assertIn(reason, opening)
        self.assertNotIn("reviewed contract prompt", body)

    def test_answer_only_fallback_reads_the_start_even_in_a_large_artifact(self):
        _, _, space = loop_for(task(status="refused_contract"), Fakes())
        reason = "The gate never calls the changed function."
        space.artifact("T1", "contract-answer", reason + "\n\n" + "quoted code\n" * 12000)
        space.event("refused", task="T1", step="contract")
        body, opening = self.draft(space)
        self.assertIn(reason, opening)
        self.assertNotIn("quoted code", body)

    def test_quarantine_summary_does_not_replace_the_reviewers_verdict(self):
        _, _, space = loop_for(task(status="quarantined", refused_why="spin detected"), Fakes())
        reason = "The check succeeds even when the output file is absent."
        space.event("refused", task="T1", step="contract", why=reason)
        space.event("quarantined", task="T1", why="spin detected")
        body, opening = self.draft(space)
        self.assertIn(reason, opening)
        self.assertNotIn("spin detected", body)

    def test_diff_json_fallback_prints_the_finding_without_quoted_evidence(self):
        _, _, space = loop_for(task(status="rejected"), Fakes())
        reason = "The changed return drops the measured width."
        answer = {"review": "REJECT", "accept": False, "observations": [], "findings": [{
            "diff_line": 7, "requirement": "goal", "problem": reason,
            "evidence": "The result is constant.\n\n```kotlin\nreturn 0\n```"}]}
        space.event("step", task="T1", step="diff_review")
        space.artifact("T1", "diff-review-answer", json.dumps(answer))
        space.event("rejected", task="T1")
        body, opening = self.draft(space)
        self.assertIn(reason, opening)
        self.assertNotIn("return 0", body)

    def test_gate_draft_keeps_console_tail_and_junit_digest(self):
        _, _, space = loop_for(task(status="rejected"), Fakes())
        console = "Build failed: see the failed test."
        digest = HEADING + "- example.Tests.width: AssertionError: expected two"
        space.artifact("T1", "gate-output", "early console " * 400 + "\n" + console + digest)
        space.event("failed", task="T1", step="gate", why="Build failed")
        body, _ = self.draft(space)
        self.assertIn(console, body)
        self.assertIn("JUnit failures:", body)
        self.assertIn("example.Tests.width: AssertionError: expected two", body)

    def test_lane_draft_opens_with_exception_after_an_earlier_review(self):
        class BrokenLoop:
            def run_task(self, row):
                space.event("step", task=row["id"], step="contract")
                space.artifact(row["id"], "contract-answer", "unrelated source")
                raise RuntimeError("cannot read the worktree")

        _, book, space = loop_for(task(), Fakes())
        run_lanes(BrokenLoop(), book, space, book.tasks())
        body, opening = self.draft(space)
        self.assertIn("RuntimeError('cannot read the worktree')", opening)
        self.assertIn("Loop step: lane", opening)
        self.assertNotIn("unrelated source", body)
