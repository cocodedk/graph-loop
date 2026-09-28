"""How a lean run ends when a repair cannot help: a green change is published with the
reviewer's findings, and a model that gave no real answer stops the run at once.
Git is real; the rest is faked (`test_lean_run.Rig`)."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import lean_run
from providers import Outcome
from test_lean_run import Rig, show


class Published(Rig):
    def test_a_green_feature_still_refused_after_the_last_repair_is_published(self):
        refused = Outcome("ok", verdict="REJECT", text="the ring ignores dark mode")
        url = self.run_it(self.builder(("ring.py", "a\n"), ("ring.py", "b\n"), ("ring.py", "c\n")),
                          suites=(True, True, True), reviews=(refused, refused, refused))
        self.assertEqual("https://example.test/pull/1", url)
        self.assertEqual(1 + lean_run.REPAIRS, len(self.prompts))
        self.assertIn("did not accept it", self.bodies[0])
        self.assertIn("the ring ignores dark mode", self.bodies[0])   # for the PR's reviewer
        self.assertEqual("c\n", show(self.repo, "lean/rest-ring", "ring.py"))
        self.assertEqual([], self.mails)                                # no stop, no person paged
        self.assertIn("lean_status: pr_open", self.spec.read_text())

    def test_an_accepted_reviews_findings_reach_the_pull_request(self):
        noted = Outcome("ok", verdict="ACCEPT", text="the ring has no dark-mode test")
        self.run_it(self.builder(("ring.py", "amber\n")), reviews=(noted,))
        self.assertIn("accepted it", self.bodies[0])
        self.assertIn("the ring has no dark-mode test", self.bodies[0])

    def test_a_clean_accept_adds_no_findings(self):
        answer = Outcome("ok", verdict="ACCEPT", text='{"review":"ACCEPT","accept":true,"findings":[]}\n')
        self.run_it(self.builder(("ring.py", "amber\n")), reviews=(answer,))
        self.assertIn("accepted it", self.bodies[0])
        self.assertNotIn("{", self.bodies[0])                          # never the bare answer line


class Stopped(Rig):
    def test_a_usage_limit_ends_the_run_without_spending_a_repair(self):
        def limited(ws, task, prompt, tree, resume="", effort=""):
            self.prompts.append(prompt)
            return Outcome("limit", text="You've hit your session limit · resets 2:10pm")
        landed = self.run_it(limited, suites=(), reviews=())
        self.assertEqual("", landed)
        self.assertEqual(1, len(self.prompts))           # no repair on an account that cannot answer
        self.assertEqual(["lean_feature_started", "lean_stopped"], self.kinds())
        self.assertIn("resets 2:10pm", self.mails[0][1])

    def test_a_reviewer_that_cannot_answer_spends_no_repair(self):
        landed = self.run_it(self.builder(("ring.py", "amber\n")), suites=(True,),
                             reviews=(Outcome("limit", text="usage limit reached"),))
        self.assertEqual("", landed)
        self.assertEqual(1, len(self.prompts))           # the work was never judged: no rebuild
        self.assertEqual("lean_stopped", self.kinds()[-1])

    def test_a_builder_that_crashed_spends_no_repair(self):
        def crashed(ws, task, prompt, tree, resume="", effort=""):
            self.prompts.append(prompt)
            return Outcome("crash", text="the builder's process died")
        self.assertEqual("", self.run_it(crashed, suites=(), reviews=()))
        self.assertEqual(1, len(self.prompts))           # only a real answer is worth a repair


if __name__ == "__main__":
    unittest.main()
