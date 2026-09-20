"""Jev's wire answer, read as a closed shape or not read as a verdict at all."""

import http.client
import json
import pathlib
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "lib"))
from provider_jev import _read, ask, question

EXPECTED_TESTS = 8
ALLOWED = ("work", "gate")


def body(**fields) -> str:
    return json.dumps({"answers": {"cause": {
        "type": "choice", "choice": "work", "confidence": 0.91, **fields}},
        "usage": {"input_tokens": 400, "output_tokens": 80, "cost": 1.9e-05}})


class ReadTest(unittest.TestCase):
    def test_one_allowed_option_is_the_verdict(self):
        out = _read(body(), ALLOWED)
        self.assertEqual(("ok", "work", 1.9e-05, 480),
                         (out.kind, out.verdict, out.cost, out.tokens))
        self.assertIn("confidence 0.91", out.text)

    def test_nothing_else_is_a_verdict(self):
        for raw in ("not json", "{}", '{"answers":{"cause":{"noul":0.9}}}',
                    '{"answers":[{"type":"choice","choice":"work"}]}',
                    body(type="noul"), body(choice="beats me"),
                    body(choice=["work"]), body(choice={"a": 1}),
                    body(veto="a field this loop does not know"),
                    ('{"error":{"code":502},"answers":{"cause":'
                     '{"type":"choice","choice":"work"}}}'),
                    ('{"answers":{"cause":{"type":"choice","choice":"gate"}},'
                     '"answers":{"cause":{"type":"choice","choice":"work"}}}')):
            with self.subTest(raw=raw):
                out = _read(raw, ALLOWED)
                self.assertFalse(out.ok)
                self.assertIsNone(out.verdict)

    def test_a_refused_answer_still_reports_what_it_cost(self):
        out = _read(body(type="noul"), ALLOWED)
        self.assertEqual((1.9e-05, 480), (out.cost, out.tokens))

    def test_only_numbers_reach_the_record(self):
        strings = body().replace("1.9e-05", '"0.02"').replace("400", '"400"')
        out = _read(strings, ALLOWED)   # the same answer, priced as a vendor string
        self.assertEqual(("ok", None, 80), (out.kind, out.cost, out.tokens))


class CallTest(unittest.TestCase):
    def test_the_request_names_the_endpoint_the_model_and_the_options(self):
        sent = {}

        def urlopen(call, timeout=None):
            sent.update(url=call.full_url, auth=call.headers["Authorization"],
                        body=json.loads(call.data))
            raise ValueError("stop here; the request is what this test reads")
        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "k"}), \
                mock.patch("urllib.request.urlopen", urlopen):
            ask(question({"record": {"files": {"a.py"}}},  # a set json refuses
                         {"work": "why"}), ALLOWED)
        self.assertEqual("https://openrouter.ai/api/alpha/decisions", sent["url"])
        self.assertEqual(("~typesafe/jev-latest", "Bearer k"),
                         (sent["body"]["model"], sent["auth"]))
        self.assertEqual("{'a.py'}", sent["body"]["state"]["record"]["files"])
        asked = sent["body"]["questions"]["cause"]
        self.assertEqual("choice", asked["type"])
        self.assertEqual(["work"], sorted(asked["criteria"]))

    def test_no_fault_escapes_to_the_driver(self):
        for fault in (http.client.RemoteDisconnected("closed"),
                      http.client.IncompleteRead(b"half"),
                      http.client.BadStatusLine("junk"), ConnectionResetError(),
                      TimeoutError(), OSError("no route"), ValueError("nonsense")):
            with self.subTest(fault=type(fault).__name__), \
                    mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "k"}), \
                    mock.patch("urllib.request.urlopen", side_effect=fault):
                out = ask('{"model":"m"}', ALLOWED)
            self.assertEqual("harness", out.kind)
            self.assertIn(type(fault).__name__, out.text)

    def test_no_key_of_ours_means_no_header_of_ours(self):
        """The gateway in front of us attaches the key; an empty header is a 401."""
        sent = {}

        def urlopen(call, timeout=None):
            sent.update(call.headers)
            raise OSError("stop here; the headers are what this test reads")
        with mock.patch.dict("os.environ", {}, clear=True), \
                mock.patch("urllib.request.urlopen", urlopen):
            ask('{"model":"m"}', ALLOWED)
        self.assertNotIn("Authorization", sent)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
