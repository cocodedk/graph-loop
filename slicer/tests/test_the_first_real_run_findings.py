"""The eight defects the first real campaign run found, each held by its case.

A campaign was planned end to end on this branch on 2026-09-18 — brief, six
branches, six specs, fourteen cards — and everything below is something that
actually went wrong in it, not something imagined. The plan-phase stop is the
ninth and lives with the graph suite; these are the slicer chain's.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "graph" / "lib"))

import branches
import speccer
import yaml
from contracts import _sources, mapping
from provider_codex import codex_text
from repair import Unreachable, repaired
from review_scope import VERDICT

EXPECTED_TESTS = 13
OK = type("V", (), {"ok": True, "why": ""})()


def spec_answer(body: str) -> str:
    return yaml.safe_dump({"result": "SPEC", "reason": "r",
                           "spec": {"name": "s", "body": body}})


PROSE = "## Goal\ng\n\n## Acceptance\na\n\n## Boundaries\nb\n"


class AbsentReviewerTest(unittest.TestCase):
    def test_a_binary_that_is_not_there_is_a_refusal_the_belt_can_walk_past(self):
        """It raised FileNotFoundError out of the review and killed the whole
        call, so one machine without codex took a campaign's reviews with it."""
        import resources
        out = codex_text("no-such-binary-anywhere", "say ACCEPT",
                         model="m", effort="high")
        self.assertTrue(resources.refused_before_reading(out.kind), out.kind)
        self.assertIn("no-such-binary-anywhere", out.text)


class FencedAnswerTest(unittest.TestCase):
    def test_a_sentence_before_the_fence_does_not_lose_the_answer(self):
        self.assertEqual({"result": "SPEC"},
                         mapping("Here is the spec:\n\n```yaml\nresult: SPEC\n```\n"))

    def test_a_bare_mapping_is_still_read(self):
        self.assertEqual({"result": "SPEC"}, mapping("result: SPEC\n"))


class ReviewShapeTest(unittest.TestCase):
    def test_the_prompts_ask_for_the_shape_the_parser_accepts(self):
        """They asked for "findings list", so a reviewer that wrote finding
        OBJECTS had a correct REJECT discarded as malformed."""
        for said in (branches.prompt, speccer.prompt):
            self.assertNotIn("findings list", said("x", pathlib.Path(".")))
        for one in (branches, speccer):
            self.assertIs(VERDICT, one.VERDICT)
        self.assertIn("never objects", VERDICT)


class WholeNoteBodyTest(unittest.TestCase):
    def test_a_spec_body_that_is_a_whole_note_is_refused(self):
        """Three of six specs came out with two front matter blocks and two
        `## Needs`, the second read as prose."""
        with self.assertRaises(ValueError) as refused:
            speccer.write_answer(spec_answer("---\nstatus: spec\n---\n\n" + PROSE),
                                 goal="g", spec_root=pathlib.Path("/tmp/claude-0/nope"),
                                 reviewer=lambda q: OK, repo=pathlib.Path("."))
        self.assertIn("whole note", str(refused.exception))


class AnchorRefusalTest(unittest.TestCase):
    def test_a_range_is_refused_by_naming_what_is_wrong_with_it(self):
        """The old refusal quoted the value against a rule it appears to
        satisfy, and the planner re-planned the goal three rounds instead."""
        with self.assertRaises(ValueError) as refused:
            _sources(["docs/spec.md:13-17"], pathlib.Path("."), [pathlib.Path(".")])
        said = str(refused.exception)
        self.assertIn("a range", said)
        self.assertIn("docs/spec.md:13", said)     # the value it should have written


class RepairRoundTest(unittest.TestCase):
    def test_a_refused_answer_is_asked_again_with_the_refusal_fed_back(self):
        asked = []

        def ask_once(question):
            asked.append(question)
            return "bad" if len(asked) < 2 else "good"

        def write(answer):
            if answer == "bad":
                raise ValueError("the answer is not YAML")
            return "written", "x"

        self.assertEqual(("written", "x"), repaired("Q", ask_once, write))
        self.assertIn("the answer is not YAML", asked[1])

    def test_a_reviewers_refusal_is_repaired_like_any_other(self):
        """The reviewer says what is wrong in words the planner could act on,
        and the layer threw them away: `write` returned `review_refused` as a
        finished state, so `repaired` returned on the spot and one refusal cost
        the whole branching (2026-09-18, the second campaign run)."""
        asked, answers = [], []

        def ask_once(question):
            asked.append(question)
            return f"answer {len(asked)}"

        def write(answer):
            answers.append(answer)
            if len(answers) < 2:
                return "review_refused", "branch two is only an input to branch one"
            return "written", "x"

        self.assertEqual(("written", "x"), repaired("Q", ask_once, write))
        self.assertIn("branch two is only an input", asked[1])
        self.assertEqual(2, len(asked))

    def test_a_reviewer_that_never_relents_ends_saying_why(self):
        state, why = repaired("Q", lambda question: "a",
                              lambda answer: ("review_refused", "invented a fact"))
        self.assertEqual(("review_refused", "invented a fact"), (state, why))

    def test_a_planner_nobody_reached_spends_no_round(self):
        asked = []

        def down(question):
            asked.append(question)
            raise Unreachable("every account refused")

        with self.assertRaises(Unreachable):
            repaired("Q", down, lambda answer: ("written", "x"))
        self.assertEqual(1, len(asked), "a silence was asked again as if it were an answer")


class AnAnsweredReviewIsNotASilentOneTest(unittest.TestCase):
    """A reviewer that answers badly still answered.

    One verdict came back `{"review":"REJECT","accept":true,"findings":[three
    correct, specific findings]}`. The parser is right to refuse that shape —
    a contradiction must never be read as an accept — but the slicer then
    reported it as `down`, "nobody judged anything", which routed it to
    `review_unavailable` and out of the repair rounds. An unambiguous REJECT
    and three findings were filed as silence (2026-09-18, the second run).

    The graph side already draws this line: `resources.refused_before_reading`
    is capacity, limit and auth — the refusals where the model never read the
    question. `malformed` is not one of them, and its own comment says so.
    """

    def reply(self, kind: str):
        import intelligence
        import providers
        out = providers.Outcome(kind, text="REJECT but accept:true, three findings")
        with unittest.mock.patch.object(providers, "codex", lambda *a, **k: out), \
                unittest.mock.patch.object(intelligence.providers, "codex",
                                           lambda *a, **k: out):
            return intelligence.review("judge this", None)

    def test_a_malformed_verdict_is_a_refusal_the_planner_can_answer(self):
        answer = self.reply("malformed")
        self.assertFalse(answer.ok)
        self.assertFalse(answer.down, "an answered review was filed as silence")
        self.assertIn("three findings", answer.why or answer.text)

    def test_a_resource_that_never_read_the_question_is_still_down(self):
        for kind in ("capacity", "limit", "auth"):
            with self.subTest(kind=kind):
                self.assertTrue(self.reply(kind).down)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
