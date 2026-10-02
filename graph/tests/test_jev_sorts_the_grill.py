"""Jev sorts the grill's questions: the person's stop the run, the builder's go on with the build, the
irrelevant are dropped. Each question is asked once per ordering of its options and the answers
averaged. No key, no answer or an unsure answer leaves every question the person's."""

import itertools
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import alert_email
import jev
import lean
import lean_git
import lean_run
import review
import tmp_root  # noqa: F401
from providers import Outcome
from test_keep import repo
from test_lean import PROFILE_TEXT
from workspace import Workspace

EXPECTED_TESTS = 9
OPTIONS = sorted(jev.WHO)


def answer(body: bytes, picks: dict[str, dict[str, float]], confidence: float = 0.9) -> str:
    """Jev's reply to `body`: every copy of question qN answers with picks[qN] as its probabilities."""
    asked = json.loads(body)["questions"]
    return json.dumps({"answers": {name: {"type": "choice", "choice": max(picks[name.rpartition("__")[0]],
                                                                          key=picks[name.rpartition("__")[0]].get),
                                          "probabilities": picks[name.rpartition("__")[0]], "confidence": confidence}
                                   for name in asked}})


def share(top: str, value: float = 0.9) -> dict[str, float]:
    rest = (1 - value) / (len(OPTIONS) - 1)
    return {option: value if option == top else rest for option in OPTIONS}


class Sort(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.mails, self.bodies = [], []
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "a.md"
        self.spec.write_text("Add a log screen.\n")
        for patched in (mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
                        mock.patch.object(alert_email, "send", lambda *a, **k: self.mails.append({**k, "body": a[0]}))):
            patched.start()
            self.addCleanup(patched.stop)

    def grill(self, questions, reply):
        def post(body):
            self.bodies.append(body)
            return reply(body)
        with mock.patch.object(review, "codex", return_value=Outcome("ok", verdict="REJECT", text=questions)), \
                mock.patch.object(jev, "post", post):
            return lean_run.grill(self.ws, repo(), [str(self.spec)], "profile.md")

    def test_every_question_is_asked_in_every_order_of_its_options(self):
        self.grill("Which file? ; Which name?", lambda body: answer(body, {"q0": share("builder"), "q1": share("builder")}))
        asked = json.loads(self.bodies[0])["questions"]
        self.assertEqual({f"q{n}__{i}" for n in (0, 1) for i in range(24)}, set(asked))
        self.assertEqual({tuple(order) for order in itertools.permutations(OPTIONS)},
                         {tuple(asked[f"q0__{i}"]["criteria"]) for i in range(24)})

    def test_builder_questions_are_handed_on_and_the_mail_says_building_goes_on(self):
        asked, handed = self.grill("Which file?; Which name?",
                                   lambda body: answer(body, {"q0": share("builder"), "q1": share("builder")}))
        self.assertEqual(("", "Which file?; Which name?"), (asked, handed))
        self.assertEqual("graph-loop is building with open questions", self.mails[0]["subject"].partition("] ")[2])

    def test_a_persons_question_stops_the_run_and_the_mail_lists_the_rest(self):
        asked, handed = self.grill("Which design?; Which name?; Why the sandbox?", lambda body: answer(
            body, {"q0": share("person"), "q1": share("builder"), "q2": share("irrelevant")}))
        self.assertEqual(("Which design?", "Which name?"), (asked, handed))
        mail = self.mails[0]
        self.assertEqual("graph-loop has questions before building", mail["subject"].partition("] ")[2])
        self.assertIn("Handed to the builder to decide: Which name?", mail["body"])
        self.assertIn("Dropped as irrelevant: Why the sandbox?", mail["body"])
        grilled = next(e for e in self.ws.events() if e["kind"] == "lean_grilled")
        self.assertEqual(("Which design?", "Which name?", "Why the sandbox?"),
                         (grilled["questions"], grilled["handed"], grilled["dropped"]))

    def test_an_unsure_answer_leaves_the_question_the_persons(self):
        for picks, confidence in ((share("builder", 0.6), 0.9), (share("builder"), 0.5)):
            with self.subTest(picks=picks, confidence=confidence):
                asked, handed = self.grill("Which name?", lambda body, picks=picks, confidence=confidence: answer(body, {"q0": picks}, confidence))
                self.assertEqual(("Which name?", ""), (asked, handed))

    def test_the_copies_are_averaged(self):
        # half the orderings say builder at 0.9, half say person at 0.9: neither reaches the threshold
        def split(body):
            whole = json.loads(answer(body, {"q0": share("builder")}))
            for name, said in whole["answers"].items():
                if int(name.rpartition("__")[2]) % 2:
                    said.update(choice="person", probabilities=share("person"))
            return json.dumps(whole)
        self.assertEqual(("Which name?", ""), self.grill("Which name?", split))
        jevs = [e for e in self.ws.events() if e["kind"] == "lean_jev"]
        self.assertEqual({}, jevs[0]["answers"])   # a tie between builder and person is no decision

    def test_a_fault_or_a_strange_answer_changes_nothing(self):
        def broken(body):
            raise OSError("down")
        for reply in (broken, lambda body: "{}", lambda body: json.dumps({"answers": {"q0__0": {}}})):
            with self.subTest(reply=reply):
                self.assertEqual(("Which name?", ""), self.grill("Which name?", reply))
        self.assertTrue(all(e["why"] for e in self.ws.events() if e["kind"] == "lean_jev"))

    def test_without_a_key_jev_is_not_called(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            self.assertEqual(("Which name?", ""), self.grill("Which name?", lambda body: self.fail("called")))
        self.assertEqual([], self.bodies)


class Run(unittest.TestCase):
    def setUp(self):
        self.repo = repo()
        (pathlib.Path(self.repo) / "profile-test.md").write_text(PROFILE_TEXT)
        (pathlib.Path(self.repo) / "CLAUDE.md").write_text("See [profile-test.md](profile-test.md).\n")
        self.ws = Workspace(tempfile.mkdtemp())
        (self.ws.root / "contact").write_text("person@example.test\n")
        self.spec = pathlib.Path(tempfile.mkdtemp()) / "log-screen.md"
        self.spec.write_text("Restyle the Log screen.\n")
        patched = mock.patch.object(lean_git, "unmerged", return_value=[])
        patched.start()
        self.addCleanup(patched.stop)

    def run_it(self, grilled):
        argv = ["--workspace", str(self.ws.root), "--repo", self.repo, "--spec", str(self.spec)]
        with mock.patch.object(lean_run, "grill", return_value=grilled), \
                mock.patch.object(lean_run, "run_feature", return_value="") as built:
            return lean.main(argv), built

    def test_only_builder_questions_go_on_to_the_build_with_them(self):
        code, built = self.run_it(("", "Which name?"))
        self.assertEqual(1, code)   # the faked build stops; what matters is that it was reached
        self.assertEqual("Which name?", built.call_args.kwargs["open_questions"])

    def test_a_persons_question_builds_nothing(self):
        code, built = self.run_it(("Which design?", "Which name?"))
        self.assertEqual(2, code)
        built.assert_not_called()


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
