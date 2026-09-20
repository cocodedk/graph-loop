"""A reviewer at capacity is replaced by the next one.

On 2026-08-31 codex answered "Selected model is at capacity" three times. One
model name was compiled into the call, so those reviews came back empty and
their changes went in unreviewed — an empty answer reading as no findings.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

# `providers` imports `review` at its foot, so `review` only resolves when
# `providers` is the module that starts the pair. This import is the load order,
# not a name this file uses — a linter removed it once as unused and the
# module stopped importing on its own.
import providers  # noqa: F401
import review
from providers import Outcome, _classify_text

EXPECTED_TESTS = 8


def answering(script):
    """A fake reviewer for BOTH agents: one scripted Outcome per model asked.

    Every entry on the belt must be faked. Patching only the codex call let a
    test walk on to claude and spend a real call — the suite went from 10
    seconds to 74."""
    seen = []

    def codex_one(_binary, _prompt, model, _cwd, _effort, _timeout):
        seen.append(model)
        return script(model)

    def claude_one(_prompt, resource, _effort, _timeout, *, cwd=""):
        seen.append(resource.model)
        return script(resource.model)

    return seen, codex_one, claude_one


class AReviewerAtCapacity(unittest.TestCase):
    def test_the_words_the_reviewer_really_answered_are_read_as_capacity(self):
        self.assertEqual("capacity", _classify_text("ERROR: Selected model is at capacity. "
                                                    "Please try a different model."))

    def test_a_models_refresh_404_alone_is_not_capacity(self):
        # Seen live, 2026-09-03T15:02:59Z: codex's own periodic background
        # "refresh available models" health check hit 404 too, moments before
        # the terminal failure below — but codex retries past this one and it
        # is not proof the review call itself gave up. Round 3 (Codex): this
        # text alone used to read as capacity, over-matching a non-fatal warning.
        self.assertIsNone(_classify_text(
            "2026-09-03T15:02:59Z ERROR codex_models_manager::manager: failed to refresh "
            "available models: unexpected status 404 Not Found: Unknown error, url: "
            "https://chatgpt.com/backend-api/codex/models?client_version=0.151.0"))

    def test_the_terminal_responses_404_is_capacity(self):
        # The actual give-up line, verbatim from the recorded call (five
        # reconnect attempts exhausted). No verdict line follows, so this fell
        # to "malformed" for want of this mark — charged like a real finding
        # instead of skipped like any other outage.
        self.assertEqual("capacity", _classify_text(
            "ERROR: unexpected status 404 Not Found: Unknown error, url: "
            "https://chatgpt.com/backend-api/codex/responses, cf-ray: a355a3d28e5bdf54-CPH"))

    def test_a_non_404_codex_error_on_the_same_url_is_not_capacity(self):
        # The URL alone is not enough — codex prints it on every call, whatever
        # the status. A 401 there is still auth's own kind (or malformed,
        # unclassified), never capacity's "another may answer".
        self.assertIsNone(_classify_text(
            "ERROR: unexpected status 401 Unauthorized: Unknown error, url: "
            "https://chatgpt.com/backend-api/codex/responses, cf-ray: abc123"))

    def test_the_next_reviewer_is_asked(self):
        seen, codex_one, claude_one = answering(lambda m: Outcome("ok", verdict="REJECT", text="a finding")
                              if m == [r.model for r in review.resources.belt('review')][1] else Outcome("capacity", text="at capacity"))
        with unittest.mock.patch.object(review, "_one_review", codex_one), \
             unittest.mock.patch.object(review, "_claude_review", claude_one):
            out = review.codex("codex", "prompt")
        self.assertEqual([r.model for r in review.resources.belt('review')][:2], seen)
        self.assertEqual("REJECT", out.verdict)

    def test_an_answer_stops_the_walk(self):
        seen, codex_one, claude_one = answering(lambda m: Outcome("ok", verdict="ACCEPT", text=""))
        with unittest.mock.patch.object(review, "_one_review", codex_one), \
             unittest.mock.patch.object(review, "_claude_review", claude_one):
            review.codex("codex", "prompt")
        self.assertEqual([next(r.model for r in review.resources.belt('review'))], seen)

    def test_a_crash_is_not_a_reason_to_ask_another_model(self):
        seen, codex_one, claude_one = answering(lambda m: Outcome("crash", text="the review did not return"))
        with unittest.mock.patch.object(review, "_one_review", codex_one), \
             unittest.mock.patch.object(review, "_claude_review", claude_one):
            review.codex("codex", "prompt")
        self.assertEqual([next(r.model for r in review.resources.belt('review'))], seen)

    def test_every_reviewer_refusing_returns_the_last_refusal(self):
        """A model at capacity is skipped wherever else it appears on the belt:
        the same model on a second account would answer the same way."""
        seen, codex_one, claude_one = answering(lambda m: Outcome("capacity", text="at capacity"))
        with unittest.mock.patch.object(review, "_one_review", codex_one), \
             unittest.mock.patch.object(review, "_claude_review", claude_one):
            out = review.codex("codex", "prompt")
        distinct = list(dict.fromkeys(r.model for r in review.resources.belt("review")))
        self.assertEqual(distinct, seen, "a model was asked twice after refusing")
        self.assertEqual("capacity", out.kind)
        self.assertIsNone(out.verdict)


class Count(unittest.TestCase):
    def test_the_file_runs_the_tests_it_says(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(found - 1, EXPECTED_TESTS)


if __name__ == "__main__":
    unittest.main()
