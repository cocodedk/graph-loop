"""Before the Codex review is paid, Jev reads a first build's diff over every ordering of its options and
refuses it when it is sure the diff has no tests or is for another spec. It may only refuse: anything
else, a revise round, a long diff, no key or a fault goes to Codex as before."""

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
import jev
import lean_judge
import tmp_root  # noqa: F401
from providers import Outcome
from test_jev_sorts_the_grill import answer
from workspace import Workspace

EXPECTED_TESTS = 5
ACCEPT = Outcome("ok", verdict="ACCEPT", text="")


def share(top: str, value: float = 0.95) -> dict[str, float]:
    rest = (1 - value) / (len(lean_judge.CHECK) - 1)
    return {option: value if option == top else rest for option in lean_judge.CHECK}


class Refuse(unittest.TestCase):
    def setUp(self):
        self.ws, self.bodies = Workspace(tempfile.mkdtemp()), []
        patched = mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
        patched.start()
        self.addCleanup(patched.stop)

    def judge(self, reply, diff="+def f(): pass\n", threads=""):
        def post(body):
            self.bodies.append(body)
            return reply(body)
        with mock.patch.object(jev, "post", post), \
                mock.patch.object(lean_judge.review, "codex", return_value=ACCEPT) as codex, \
                mock.patch.object(lean_judge.lean_calls, "started", return_value={"effort": "medium"}):
            return lean_judge.judge(self.ws, "rest-ring", "the spec", diff, "/nowhere", threads=threads), codex

    def test_a_sure_refusal_is_the_rounds_reject_and_codex_is_not_paid(self):
        for choice in ("no_tests", "wrong_spec"):
            with self.subTest(choice=choice):
                verdict, codex = self.judge(lambda body, choice=choice: answer(body, {"verdict": share(choice)}))
                self.assertEqual(("REJECT", lean_judge.FOUND[choice]), (verdict.verdict, verdict.text))
                codex.assert_not_called()
        self.assertEqual(24, len(json.loads(self.bodies[0])["questions"]))
        self.assertEqual({"spec": "the spec", "diff": "+def f(): pass\n"}, json.loads(self.bodies[0])["state"])

    def test_an_accept_is_codexs_to_give(self):
        verdict, codex = self.judge(lambda body: answer(body, {"verdict": share("accept")}))
        self.assertEqual("ACCEPT", verdict.verdict)
        codex.assert_called_once()

    def test_an_unsure_refusal_goes_to_codex(self):
        for picks, confidence in ((share("no_tests", 0.6), 0.9), (share("no_tests"), 0.5)):
            with self.subTest(picks=picks, confidence=confidence):
                _, codex = self.judge(lambda body, p=picks, c=confidence: answer(body, {"verdict": p}, c))
                codex.assert_called_once()

    def test_a_revise_round_or_a_long_diff_skips_jev(self):
        sure = lambda body: answer(body, {"verdict": share("no_tests")})
        self.judge(sure, threads="fix the name")
        self.judge(sure, diff="+x\n" * lean_judge.JEV_LIMIT)
        self.assertEqual([], self.bodies)

    def test_a_fault_goes_to_codex(self):
        def broken(body):
            raise OSError("down")
        _, codex = self.judge(broken)
        codex.assert_called_once()


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS + 1, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
