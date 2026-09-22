"""Mixed build belts and independent reviews, without a real provider call."""

import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import model_router
import models
import providers
import real_calls
import resources
from provider_codex import codex_text
from router_probe import CARD, CATALOG, Decisions

CATALOG = {**CATALOG, "GRAPH_BUILDERS": "gpt-6-astra,claude-sonnet-5,claude-opus-5"}


class CodexBuilders(unittest.TestCase):
    def setUp(self):
        catalog = patch.dict("os.environ", CATALOG)
        catalog.start()
        self.addCleanup(catalog.stop)

    def test_default_keeps_astra_behind_the_claude_builders(self):
        with patch.dict("os.environ", {"GRAPH_BUILDERS": ""}):
            self.assertEqual(("claude-sonnet-5", "gpt-6-astra"), (models.builders()[0], models.builders()[-1]))

    def test_codex_is_not_duplicated_across_claude_accounts(self):
        with patch("accounts.available", return_value=["one", "two"]):
            belt = resources.belt("build")
        self.assertEqual([resources.Resource("codex", None, "gpt-6-astra")],
                         [r for r in belt if r.agent == "codex"])
        self.assertEqual(4, sum(r.agent == "claude" for r in belt))

    def test_router_can_select_astra_and_fall_back_to_it(self):
        with patch("urllib.request.urlopen", side_effect=Decisions(model="gpt-6-astra")):
            choice = model_router.choose(CARD, "build")
        self.assertEqual(("codex", "gpt-6-astra", "jev"),
                         (choice.resource.agent, choice.resource.model, choice.source))
        with patch.dict("os.environ", {"GRAPH_ROUTER": "off"}):
            self.assertEqual(choice.resource, model_router.choose(CARD, "build").resource)

    def test_planning_and_guarded_live_builds_stay_on_claude(self):
        self.assertTrue(all(r.agent == "claude" for r in resources.belt("plan")))
        live = {**CARD, "gate_has_side_effects": True}
        self.assertTrue(all(r.agent == "claude" for r in model_router.candidates("build", task=live)))
        with patch("real_calls.codex_text") as call:
            out = self.build(guard="helper only")
        self.assertEqual("harness", out.kind)
        call.assert_not_called()

    def build(self, **kwargs):
        return real_calls._real_build("build", account=None, cwd="/card/tree", files=["a.py"],
                                      tools="", denies="", model="gpt-6-astra", effort="high",
                                      **{"guard": "", **kwargs})

    def test_build_dispatch_is_confined_to_worktree(self):
        done = subprocess.CompletedProcess([], 0, "DONE", "")
        with patch("provider_codex._run", return_value=done) as run, patch("real_calls.claude") as claude:
            self.assertTrue(self.build().ok)
        claude.assert_not_called()
        argv = run.call_args.args[0]
        self.assertEqual("workspace-write", argv[argv.index("--sandbox") + 1])
        self.assertEqual("/card/tree", argv[argv.index("--cd") + 1])
        self.assertEqual("/card/tree", run.call_args.kwargs["cwd"])
        self.assertEqual(providers.BUILD_TIMEOUT, run.call_args.args[3])
        for setting in ('approval_policy="never"', "sandbox_workspace_write.writable_roots=[]",
                        "sandbox_workspace_write.exclude_slash_tmp=true",
                        "sandbox_workspace_write.exclude_tmpdir_env_var=true",
                        "sandbox_workspace_write.network_access=false"):
            self.assertIn(setting, argv)
        self.assertIn("--ignore-user-config", argv)
        self.assertNotIn("--add-dir", argv)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)

    def test_no_worktree_never_launches_a_writable_call(self):
        with patch("provider_codex._run") as run:
            out = codex_text("codex", "build", model="gpt-6-astra", effort="medium", write=True)
        self.assertEqual("harness", out.kind)
        run.assert_not_called()

    def test_review_transport_stays_read_only(self):
        with patch("provider_codex._run", return_value=subprocess.CompletedProcess([], 0, "text", "")) as run:
            codex_text("codex", "review", model="gpt-6-astra", effort="medium", cwd="/card/tree")
        argv = run.call_args.args[0]
        self.assertEqual("read-only", argv[argv.index("--sandbox") + 1])

    def test_no_same_model_on_any_agent_or_account(self):
        belt = [resources.Resource("codex", None, "gpt-6-astra"),
                resources.Resource("claude", "other", "gpt-6-astra"),
                resources.Resource("codex", None, "gpt-5.6-sol")]
        with patch("resources.belt", return_value=belt):
            self.assertEqual(belt[-1:], model_router.candidates("review", "gpt-6-astra"))

    def test_astra_build_is_reviewed_by_sol_then_claude_on_capacity(self):
        seen = []

        def codex_review(_binary, _prompt, model, *_args):
            seen.append(model)
            return providers.Outcome("capacity")

        def claude_review(_prompt, resource, *_args, **_kwargs):
            seen.append(resource.model)
            return providers.Outcome("ok", verdict="ACCEPT")

        with patch("real_calls._routed_task", return_value={**CARD, "builder_model": "gpt-6-astra"}), \
             patch.dict("os.environ", {"GRAPH_ROUTER": "off"}), \
             patch("review._one_review", side_effect=codex_review), \
             patch("review._claude_review", side_effect=claude_review):
            out = real_calls._real_review("review", cwd="/card/tree")
        self.assertEqual("ACCEPT", out.verdict)
        self.assertEqual(["gpt-5.6-sol", "claude-opus-5"], seen)

    def test_only_astra_reviewers_fail_closed_for_an_astra_build(self):
        with patch.dict("os.environ", {"GRAPH_REVIEWERS": "gpt-6-astra",
                                       "GRAPH_CLAUDE_REVIEWERS": "gpt-6-astra"}), \
             patch("urllib.request.urlopen") as call, self.assertRaises(LookupError):
            model_router.choose(CARD, "review", builder_model="gpt-6-astra")
        call.assert_not_called()
