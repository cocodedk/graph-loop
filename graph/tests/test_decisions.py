"""Several typed questions in one call, read as a closed shape or not read at all."""

import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
from decisions import ask

EXPECTED_TESTS = 13
QUESTIONS = {
    "one": {"instructions": "Which side?", "criteria": {"left": "the left", "right": "the right"}},
    "two": {"instructions": "Which size?", "criteria": {"big": "large", "small": "little"}},
}


def reply(one=None, two=None, **beside) -> str:
    """A well-formed reply unless a test bends one part of it."""
    answers = {
        "one": one or {"type": "choice", "choice": "left", "confidence": 0.9,
                       "probabilities": {"left": 0.9, "right": 0.1}},
        "two": two or {"type": "choice", "choice": "big", "confidence": 0.8,
                       "probabilities": {"big": 0.8, "small": 0.2}}}
    return json.dumps({"answers": {f"{qid}__{i}": answer for qid, answer in answers.items()
                                    for i in range(2)}, **({"usage": {
        "input_tokens": 300, "output_tokens": 40, "cost": 2.5e-05}} | beside)})


def scripted(text: str, sent: list | None = None):
    def post(body: str) -> str:
        if sent is not None:
            sent.append(body)
        return text
    return post


def refused(test: unittest.TestCase, text: str):
    out = ask({"s": 1}, QUESTIONS, scripted(text))
    test.assertFalse(out.ok)
    test.assertTrue(out.why)
    test.assertEqual({}, out.answers)
    return out


class AskTest(unittest.TestCase):
    def test_a_well_formed_reply_answers_every_question(self):
        sent = []
        out = ask({"s": 1}, QUESTIONS, scripted(reply(), sent))
        self.assertTrue(out.ok)
        self.assertEqual("", out.why)
        asked = json.loads(sent[0])
        self.assertEqual(["one__0", "one__1", "two__0", "two__1"], sorted(asked["questions"]))
        self.assertEqual({"choice": "left", "confidence": 0.9}, out.answers["one"])
        self.assertEqual({"choice": "big", "confidence": 0.8}, out.answers["two"])
        self.assertGreater(out.seconds, 0)
        self.assertEqual(2.5e-05, out.cost)
        self.assertEqual(1, len(sent))     # one call for both questions

    def test_the_request_carries_the_state_and_each_questions_own_criteria(self):
        sent = []
        ask({"s": {"day": {1, 2}}}, QUESTIONS, scripted(reply(), sent))   # a set json refuses
        asked = json.loads(sent[0])
        self.assertEqual("{1, 2}", asked["state"]["s"]["day"])
        self.assertEqual({"left", "right"}, set(asked["questions"]["one__0"]["criteria"]))
        self.assertEqual("choice", asked["questions"]["two__0"]["type"])
        self.assertEqual("Which size?", asked["questions"]["two__0"]["instructions"])

    def test_a_question_left_unanswered_refuses_the_whole_call(self):
        whole = json.loads(reply())
        for name in ("two__0", "two__1"):
            del whole["answers"][name]
        self.assertTrue(refused(self, json.dumps(whole)).why)

    def test_an_answer_nobody_asked_for_refuses_the_whole_call(self):
        extra = json.loads(reply())
        extra["answers"]["three"] = {"type": "choice", "choice": "left"}
        refused(self, json.dumps(extra))

    def test_a_choice_outside_its_own_criteria_is_refused(self):
        # "big" is a real choice, but of the other question in this call
        for choice in ("middle", "big", ["left"]):
            with self.subTest(choice=choice):
                refused(self, reply(one={"type": "choice", "choice": choice, "confidence": 0.9,
                                        "probabilities": {"left": 0.9, "right": 0.1}}))

    def test_a_repeated_key_is_refused(self):
        # each of these reads as a whole, valid answer if the last duplicate wins
        refused(self, reply().replace('{"answers": {', '{"answers": {}, "answers": {', 1))
        refused(self, reply().replace('"choice": "left"', '"choice": "right", "choice": "left"'))

    def test_an_error_beside_the_answers_is_refused(self):
        refused(self, reply(error={"code": 502}))

    def test_malformed_json_is_refused(self):
        for text in ("not json", "", "[]", "null", '{"answers":'):
            with self.subTest(text=text):
                refused(self, text)

    def test_a_field_outside_the_answer_schema_is_refused(self):
        refused(self, reply(two={"type": "choice", "choice": "big", "veto": True}))
        refused(self, reply(two={"type": "text", "choice": "big"}))    # not a choice answer

    def test_a_post_that_raises_costs_the_call_and_nothing_escapes(self):
        def post(_body: str) -> str:
            raise TimeoutError("no answer")
        out = ask({"s": 1}, QUESTIONS, post)
        self.assertFalse(out.ok)
        self.assertIn("TimeoutError", out.why)

    def test_a_refused_reply_still_reports_what_it_cost(self):
        out = refused(self, reply(one={"type": "choice", "choice": "middle"}))
        self.assertEqual(2.5e-05, out.cost)

    def test_four_orders_average_by_label_and_one_missing_answer_refuses_all(self):
        questions = {"one__0": {"instructions": "Which?", "criteria": {
            "a": "first", "b": "second", "c": "third"}}, **QUESTIONS}
        sent = []

        def post(body):
            asked = json.loads(body)["questions"]
            sent.append(asked)
            answers = json.loads(reply())["answers"]
            for i in range(4):
                answers[f"one__0__{i}"] = {
                    "type": "choice", "choice": "a" if i == 0 else "b", "confidence": 0.8,
                    "probabilities": {"c": 0, "b": 0.1 if i == 0 else 0.8,
                                      "a": 0.9 if i == 0 else 0.2}}
            return json.dumps({"answers": answers, "usage": {"cost": 0.01}})
        out = ask({}, questions, post)
        self.assertTrue(out.ok)
        self.assertEqual({"choice": "b", "confidence": 0.8}, out.answers["one__0"])
        self.assertEqual(0.01, out.cost)
        self.assertEqual(1, len(sent))
        self.assertEqual(8, len(sent[0]))
        incomplete = json.loads(post(json.dumps({"questions": sent[0]})))
        del incomplete["answers"]["one__0__3"]
        out = ask({}, questions, scripted(json.dumps(incomplete)))
        self.assertFalse(out.ok)
        self.assertEqual({}, out.answers)
        self.assertEqual(0.01, out.cost)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
