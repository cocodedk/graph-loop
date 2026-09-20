"""alert-watcher.sh run for real with a stubbed messenger: delivery is only
a SendMessage call in the record, to WATCHER, carrying the flags, answered
without error — model prose proves nothing, a ticking counter is not news,
nothing is recorded when nobody was reached, and every attempt keeps its own
call record."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

DRIVE = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_TESTS = 8


def age(path: pathlib.Path, minutes: int) -> None:
    then = time.time() - minutes * 60
    os.utime(path, (then, then))


def record_for(flags_line: str, message: str | None = None, success: bool = True) -> str:
    send = {"message": {"content": [{"type": "tool_use", "id": "t1", "name": "SendMessage",
                                     "input": {"to": "WATCHER",
                                               "message": message if message is not None
                                               else f"the board went red:\n{flags_line}"}}]}}
    result = {"message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                       "content": json.dumps({"success": success,
                                                              "message": "delivered" if success
                                                              else "No agent named WATCHER"})}]}}
    return json.dumps(send) + "\n" + json.dumps(result) + "\n"


class Rig(unittest.TestCase):
    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.camp, ignore_errors=True)
        self.stub = self.camp / "bin"
        self.stub.mkdir()
        self.check = self.camp / "check.txt"

    def claude_answers(self, record: str, rc: int = 0):
        fixture = self.camp / "fixture.jsonl"
        fixture.write_text(record, "utf-8")
        (self.stub / "claude").write_text(
            f"#!/bin/bash\ncat > {self.camp}/prompt.txt\ncat {fixture}\nexit {rc}\n")
        (self.stub / "claude").chmod(0o755)

    def claude_faithful(self, rc: int = 0, to: str = "WATCHER"):
        """A stub that obeys the prompt: it sends EXACTLY the body between the
        --- markers, the way an honest messenger would, to the given `to`."""
        helper = self.camp / "faithful.py"
        helper.write_text(
            "import json, sys\n"
            "text = sys.stdin.read()\n"
            "body = text.split('---\\n')[1].rsplit('\\n---', 1)[0]\n"
            "send = {'message': {'content': [{'type': 'tool_use', 'id': 't1',\n"
            "        'name': 'SendMessage', 'input': {'to': " + repr(to) + ", 'message': body}}]}}\n"
            "res = {'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't1',\n"
            "       'content': json.dumps({'success': True})}]}}\n"
            "print(json.dumps(send)); print(json.dumps(res))\n", "utf-8")
        real = shutil.which("python3")
        (self.stub / "claude").write_text(
            f"#!/bin/bash\ntee {self.camp}/prompt.txt | \"{real}\" {helper}\nexit {rc}\n")
        (self.stub / "claude").chmod(0o755)

    def run_alert(self, flags: str, email_rc: int = 1, extra_env: dict | None = None) -> int:
        # the real python3 serves identity and proof calls; lib/alert_email.py
        # is intercepted so no test ever sends a real email
        real = shutil.which("python3")
        # and what the email was handed is kept in mailed.txt: the flags a run
        # read and the file it mails can drift apart while the messenger runs
        (self.stub / "python3").write_text(
            "#!/bin/bash\n"
            f'case "$*" in *alert_email.py*) cat "${{@: -1}}" > {self.camp}/mailed.txt;'
            f' exit {email_rc} ;; *) exec "{real}" "$@" ;; esac\n')
        (self.stub / "python3").chmod(0o755)
        self.check.write_text(flags + "\n", "utf-8")
        env = dict(os.environ, PATH=f"{self.stub}:{os.environ['PATH']}")
        if extra_env:
            env.update(extra_env)
        return subprocess.run(["bash", str(DRIVE / "alert-watcher.sh"),
                               str(self.camp), str(self.check)],
                              env=env, check=False, capture_output=True, text=True).returncode

    def log(self) -> str:
        return (self.camp / "supervisor.log").read_text("utf-8")


class AlertWatcherTest(Rig):
    def test_only_a_proven_send_of_the_exact_body_is_a_delivery(self):
        line = "  !! red   (since 2026-08-31T10:00+0200)"
        self.claude_faithful()
        self.assertEqual(0, self.run_alert(line))
        self.assertIn("delivered to WATCHER", self.log())
        self.assertTrue((self.camp / "watcher-alert.last").exists())

    def test_model_prose_saying_delivered_is_not_a_delivery(self):
        prose = json.dumps({"message": {"content": [{"type": "text", "text": "DELIVERED"}]}})
        self.claude_answers(prose + "\n")
        self.assertEqual(1, self.run_alert("  !! red   (since 2026-08-31T10:00+0200)"))
        self.assertNotIn("delivered to WATCHER", self.log())
        self.assertFalse((self.camp / "watcher-alert.last").exists())

    def test_a_flags_only_message_is_not_the_instructed_body(self):
        # the flags without the instruction header is NOT the verbatim body
        line = "  !! red   (since 2026-08-31T10:00+0200)"
        self.claude_answers(record_for(line))                   # header + flags, not the body
        self.assertEqual(1, self.run_alert(line))
        self.claude_answers(record_for(line, message=line))     # bare flags
        self.assertEqual(1, self.run_alert(line))
        self.assertNotIn("delivered to WATCHER", self.log())

    def test_a_send_answered_success_false_is_not_a_delivery(self):
        # the real refusal shape: {"success": false} with no is_error flag
        line = "  !! red   (since 2026-08-31T10:00+0200)"
        self.claude_answers(record_for(line, success=False))
        self.assertEqual(1, self.run_alert(line))
        self.assertNotIn("delivered to WATCHER", self.log())
        self.assertFalse((self.camp / "watcher-alert.last").exists())

    def test_a_proven_send_from_a_crashed_messenger_is_not_trusted(self):
        line = "  !! red   (since 2026-08-31T10:00+0200)"
        self.claude_faithful(rc=3)
        self.assertEqual(1, self.run_alert(line))
        self.assertFalse((self.camp / "watcher-alert.last").exists())

    def test_a_ticking_counter_is_the_same_standing_red_and_records_are_kept(self):
        first = "  !! quiet for 25 minutes   (since 2026-08-31T10:00+0200)"
        self.claude_faithful()
        self.assertEqual(0, self.run_alert(first))
        self.assertEqual(0, self.run_alert(first.replace("25", "40")))     # deduped
        self.assertEqual(1, self.log().count("delivered to WATCHER"))
        other = "  !! T26 is stuck   (since 2026-08-31T10:00+0200)"
        self.assertEqual(0, self.run_alert(other))                         # a new flag is news
        self.assertEqual(2, self.log().count("delivered to WATCHER"))
        # every attempt kept its own call record
        self.assertEqual(2, len(list(self.camp.glob("messenger-*.jsonl"))))


class WholeFileTest(Rig):
    def test_a_flag_beyond_two_thousand_bytes_still_reaches_the_messenger(self):
        filler = "  !! " + "x" * 2400 + "   (since 2026-08-31T10:00+0200)"
        tail = "  !! the-trailing-flag   (since 2026-08-31T10:05+0200)"
        flags = filler + "\n" + tail
        self.claude_faithful()
        self.assertEqual(0, self.run_alert(flags))
        prompt = (self.camp / "prompt.txt").read_text("utf-8")
        self.assertIn("the-trailing-flag", prompt)              # nothing capped away


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
