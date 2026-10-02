"""The lean loop's grill: the specs are read before anything is built."""

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import alert_email
import lean_run
import review
import tmp_root  # noqa: F401
from providers import Outcome
from test_keep import repo
from workspace import Workspace


class Grill(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.mails, self.spec = [], pathlib.Path(tempfile.mkdtemp()) / "a.md"
        self.spec.write_text("Make it blue, and make it red.\n")

    def grill(self, answer):
        with mock.patch.object(review, "codex", return_value=answer) as call, \
                mock.patch.object(alert_email, "send", lambda *a, **k: self.mails.append(k)):
            questions, _, self.refused = lean_run.grill(self.ws, repo(), [str(self.spec)], "profile.md")
        self.assertIn("Make it blue, and make it red.", call.call_args.args[1])
        self.prompt = call.call_args.args[1]
        return questions

    def test_questions_are_emailed_and_returned(self):
        self.assertEqual("Blue or red?", self.grill(Outcome("ok", verdict="REJECT", text="Blue or red?")))
        self.assertTrue(self.refused)
        self.assertEqual("graph-loop has questions before building", self.mails[0]["subject"].partition("] ")[2])

    def test_clear_specs_ask_nothing(self):
        self.assertEqual("", self.grill(Outcome("ok", verdict="ACCEPT")))
        self.assertEqual([], self.mails)

    def test_the_grill_is_told_the_suite_has_network_but_no_docker(self):
        self.grill(Outcome("ok", verdict="ACCEPT"))
        self.assertNotIn("no network. Refuse", self.prompt)    # the sandbox keeps the network
        self.assertIn("with its network, an empty home and no Docker", self.prompt)   # what the gate box gives
        self.assertIn("your own read-only sandbox may be unable to run it", self.prompt)

    def test_the_grill_is_told_the_builders_grant_follows_the_suite(self):
        # a suite that runs chmod grants chmod: the grill must not rule it out
        self.grill(Outcome("ok", verdict="ACCEPT"))
        self.assertIn("runs git, the suite and the programs the suite uses", self.prompt)
        self.assertNotIn("chmod", self.prompt)

    def test_the_grill_interrogates_a_user_interface_before_building(self):
        self.grill(Outcome("ok", verdict="ACCEPT"))
        for asked in ("user interface", "be critical of every word", "the whole journey",
                      "every page and state", "empty, loading and error", "design reference"):
            self.assertIn(asked, self.prompt)

    def test_the_grill_is_told_to_ask_the_crucial_questions_first(self):
        self.grill(Outcome("ok", verdict="ACCEPT"))
        self.assertIn("Ask only the crucial questions, the ones whose answer changes what is built, "
                      "the most important first", self.prompt)

    def test_the_grill_reads_the_projects_lessons_beside_the_spec(self):
        (self.spec.parent / "lessons.md").write_text("- Say which earlier tests the builder may change.\n")
        self.grill(Outcome("ok", verdict="ACCEPT"))
        self.assertIn("Lessons from earlier runs of this project (hints to check, never proof)", self.prompt)
        self.assertIn("Say which earlier tests the builder may change.", self.prompt)

    def test_without_lessons_the_grill_prompt_has_none(self):
        self.grill(Outcome("ok", verdict="ACCEPT"))
        self.assertNotIn("Lessons from earlier runs", self.prompt)

    def test_every_mail_names_its_project(self):
        inside = pathlib.Path(repo()) / "scratchpad" / "lean"      # a workspace in a checkout
        inside.mkdir(parents=True)
        (inside / "contact").write_text("person@example.test\n")
        with mock.patch.object(alert_email, "send", lambda *a, **k: self.mails.append(k)):
            Workspace(str(inside)).mail_person("graph-loop: hello", "body")
            self.ws.event("repository_declared", repo="/somewhere/fits-api")
            self.ws.mail_person("graph-loop: hello", "body")
        self.assertEqual(f"[{inside.parents[1].name}] graph-loop: hello", self.mails[0]["subject"])
        self.assertEqual("[fits-api] graph-loop: hello", self.mails[1]["subject"])

    def test_a_grill_that_did_not_answer_stops_too(self):
        self.assertIn("did not answer", self.grill(Outcome("malformed")))
        self.assertFalse(self.refused)   # no answer is no round
        self.assertEqual("graph-loop could not read the specs before building", self.mails[0]["subject"].partition("] ")[2])



if __name__ == "__main__":
    unittest.main()
