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
            questions = lean_run.grill(self.ws, repo(), [str(self.spec)], "profile.md")
        self.assertIn("Make it blue, and make it red.", call.call_args.args[1])
        self.prompt = call.call_args.args[1]
        return questions

    def test_questions_are_emailed_and_returned(self):
        self.assertEqual("Blue or red?", self.grill(Outcome("ok", verdict="REJECT", text="Blue or red?")))
        self.assertEqual("graph-loop has questions before building", self.mails[0]["subject"].partition("] ")[2])

    def test_clear_specs_ask_nothing(self):
        self.assertEqual("", self.grill(Outcome("ok", verdict="ACCEPT")))
        self.assertEqual([], self.mails)

    def test_the_grill_is_told_the_suite_has_network_and_docker(self):
        self.grill(Outcome("ok", verdict="ACCEPT"))
        self.assertNotIn("no network. Refuse", self.prompt)    # the sandbox keeps the network
        self.assertIn("with its network and Docker", self.prompt)
        self.assertIn("your own read-only sandbox may be unable to run it", self.prompt)

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
        self.assertEqual("graph-loop could not read the specs before building", self.mails[0]["subject"].partition("] ")[2])



if __name__ == "__main__":
    unittest.main()
