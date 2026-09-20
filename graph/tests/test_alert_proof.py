"""lib/alert_proof.proven against the real messenger call-record shape.

The fixture (tests/fixtures/messenger-real-two-line.jsonl) is the SendMessage
tool_use and its tool_result, copied verbatim from a real messenger run
(scratchpad/graph-campaigns/current/messenger-20260903-081817-2008870.jsonl,
lines 13-14; no secrets in those two lines). It shows the real shape: `to`
came back "WATCHER [b362c3]" — ListAgents had two sessions named WATCHER
(a background shell and an interactive one) and the model disambiguated —
so an exact-string match against "WATCHER" never fires, and every proven
delivery reads as unproven. That is why the emails fired while the messages
were arriving.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import unittest

GRAPH = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRAPH / "lib"))
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from alert_proof import proven

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "messenger-real-two-line.jsonl"

EXPECTED_TESTS = 14


def real_body() -> str:
    """The exact message the real record's SendMessage call carried."""
    first = json.loads(FIXTURE.read_text("utf-8").splitlines()[0])
    return first["message"]["content"][0]["input"]["message"]


def record_for(to: str, message: str, tmp_path: pathlib.Path, success: bool = True) -> str:
    send = {"message": {"content": [{"type": "tool_use", "id": "t1", "name": "SendMessage",
                                     "input": {"to": to, "message": message}}]}}
    result = {"message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                       "content": json.dumps({"success": success})}]}}
    path = tmp_path / "record.jsonl"
    path.write_text(json.dumps(send) + "\n" + json.dumps(result) + "\n", "utf-8")
    return str(path)


class AlertProofTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_a_real_send_to_the_bracketed_session_id_is_proven(self):
        # to: "WATCHER [b362c3]" — the bare target name plus ListAgents'
        # disambiguating suffix, because two sessions shared the name
        self.assertTrue(proven(str(FIXTURE), real_body()))

    def test_a_refused_send_is_not_proven(self):
        record = record_for("WATCHER [b362c3]", "the board went red", success=False, tmp_path=self.tmp)
        self.assertFalse(proven(record, "the board went red"))

    def test_a_paraphrased_body_is_not_proven(self):
        record = record_for("WATCHER [b362c3]", "the board is red, go look", tmp_path=self.tmp)
        self.assertFalse(proven(record, "the board went red"))

    def test_whitespace_layout_difference_breaks_the_match(self):
        # verbatim means verbatim: proof is a stripped exact match, so
        # different internal whitespace is a different body, not the same
        # one laid out differently — the earlier normalize-then-compare
        # loosened this without evidence from a live fixture that needed it
        record = record_for("WATCHER [b362c3]", "the board\nwent   red", tmp_path=self.tmp)
        self.assertFalse(proven(record, "the board\n  went red"))

    def test_a_send_to_a_different_target_does_not_match(self):
        # WATCHER-STANDIN's bracketed id must never prove a send meant for WATCHER
        record = record_for("WATCHER-STANDIN [a1b2c3]", "the board went red", tmp_path=self.tmp)
        self.assertFalse(proven(record, "the board went red", target="WATCHER"))

    def test_the_target_parameter_selects_which_session_counts(self):
        record = record_for("WATCHER-STANDIN [a1b2c3]", "the board went red", tmp_path=self.tmp)
        self.assertTrue(proven(record, "the board went red", target="WATCHER-STANDIN"))

    def test_a_malformed_bracket_id_is_not_proven(self):
        # the id must be exactly six hex digits, not any text after "TARGET ["
        record = record_for("WATCHER [x]", "the board went red", tmp_path=self.tmp)
        self.assertFalse(proven(record, "the board went red"))

    def test_a_null_tool_use_id_does_not_correlate(self):
        # a tool_use with no id (id: null) must never let a tool_result whose
        # own tool_use_id is also null "prove" the send by matching None to None
        send = {"message": {"content": [{"type": "tool_use", "id": None, "name": "SendMessage",
                                         "input": {"to": "WATCHER", "message": "the board went red"}}]}}
        result = {"message": {"content": [{"type": "tool_result", "tool_use_id": None,
                                           "content": json.dumps({"success": True})}]}}
        record = self.tmp / "record.jsonl"
        record.write_text(json.dumps(send) + "\n" + json.dumps(result) + "\n", "utf-8")
        self.assertFalse(proven(str(record), "the board went red"))

    def test_a_non_string_tool_use_id_does_not_crash_or_correlate(self):
        # a hostile/malformed tool_use_id (a list, say) must not raise trying
        # to hash it against `sent`, and must not count as a correlation
        send = {"message": {"content": [{"type": "tool_use", "id": "t1", "name": "SendMessage",
                                         "input": {"to": "WATCHER", "message": "the board went red"}}]}}
        result = {"message": {"content": [{"type": "tool_result", "tool_use_id": [1, 2, 3],
                                           "content": json.dumps({"success": True})}]}}
        record = self.tmp / "record.jsonl"
        record.write_text(json.dumps(send) + "\n" + json.dumps(result) + "\n", "utf-8")
        self.assertFalse(proven(str(record), "the board went red"))


class MalformedShapeTest(unittest.TestCase):
    """Valid JSON whose containers are not the object shape this code
    expects — event, message, input, or a result payload — must not crash
    the reader; a wrong shape proves nothing rather than raising."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, *lines: object) -> str:
        path = self.tmp / "record.jsonl"
        path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", "utf-8")
        return str(path)

    def test_a_non_object_event_does_not_crash(self):
        record = self.write([1, 2, 3])
        self.assertFalse(proven(record, "the board went red"))

    def test_a_non_object_message_does_not_crash(self):
        record = self.write({"message": "oops"})
        self.assertFalse(proven(record, "the board went red"))

    def test_a_non_object_tool_use_input_does_not_crash(self):
        record = self.write({"message": {"content": [
            {"type": "tool_use", "name": "SendMessage", "id": "t1", "input": 42}]}})
        self.assertFalse(proven(record, "the board went red"))

    def test_a_bare_string_result_payload_does_not_crash(self):
        send = {"message": {"content": [{"type": "tool_use", "id": "t1", "name": "SendMessage",
                                         "input": {"to": "WATCHER", "message": "the board went red"}}]}}
        result = {"message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                           "content": '"just text"'}]}}
        record = self.write(send, result)
        self.assertFalse(proven(record, "the board went red"))


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
