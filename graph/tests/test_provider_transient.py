"""Provider weather is a capacity outage; a broken process is still a crash."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

from providers import claude, codex_text


def answer(*, returncode=0, **fields):
    body = {"is_error": True, "result": "provider failed", "total_cost_usd": 0.5,
            "usage": {"input_tokens": 10, "output_tokens": 20},
            "permission_denials": [], "session_id": "kept-session", **fields}
    done = subprocess.CompletedProcess([], returncode, json.dumps(body), "")
    with patch("providers._run", return_value=done):
        return claude("unused", "prompt", account="work")


class TransientAnswerTest(unittest.TestCase):
    def test_api_error_status_is_evidence_without_error_words(self):
        for status in (500, 502, 503, 504, 599):
            with self.subTest(status=status):
                out = answer(api_error_status=status)
                self.assertEqual("capacity", out.kind)
                self.assertFalse(out.consumes_attempt)
                self.assertEqual((0.5, 30, "kept-session"),
                                 (out.cost, out.tokens, out.session))

    def test_api_error_status_alone_is_not_success(self):
        self.assertEqual("capacity", answer(is_error=False, api_error_status=503).kind)

    def test_transient_result_words_are_provider_failures(self):
        for message in ("API Error: 500 Internal server error", "HTTP 502 Bad Gateway",
                        "HTTP/1.1 503", "unexpected status 504 Gateway Timeout",
                        "Connection reset by peer", "ECONNRESET", "Gateway timeout",
                        "Overloaded", "Service unavailable"):
            with self.subTest(message=message):
                self.assertEqual("capacity", answer(result=message).kind)

    def test_successful_work_can_discuss_server_errors(self):
        out = answer(is_error=False, result="Fixed HTTP 500, overloaded and service unavailable tests")
        self.assertEqual("ok", out.kind)

    def test_other_statuses_and_ordinary_numbers_are_not_weather(self):
        for fields in ({"api_error_status": 400}, {"api_error_status": 600},
                       {"api_error_status": None}, {"api_error_status": {}},
                       {"result": "processed 500 records before crashing"},
                       {"result": "HTTP 5000 is not a status"}):
            with self.subTest(fields=fields):
                self.assertEqual("crash", answer(**fields).kind)

    def test_a_process_death_and_malformed_output_stay_charged_kinds(self):
        self.assertEqual("crash", answer(returncode=-9, is_error=False).kind)
        done = subprocess.CompletedProcess([], 1, "half an answer", "")
        with patch("providers._run", return_value=done):
            self.assertEqual("malformed", claude("unused", "prompt", account="work").kind)

    def test_codex_uses_the_same_transient_words_only_after_failure(self):
        for code, kind in ((1, "capacity"), (0, "ok")):
            with self.subTest(code=code):
                done = subprocess.CompletedProcess([], code, "HTTP 503 Service Unavailable", "")
                with patch("provider_codex._run", return_value=done):
                    out = codex_text("unused", "prompt", model="test", effort="medium")
                self.assertEqual(kind, out.kind)


if __name__ == "__main__":
    unittest.main()
