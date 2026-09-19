"""Heartbeat-based routing: alert-watcher.sh targets WATCHER while fresh, its stand-in
WATCHER-STANDIN once stale — a target change is news, so identical flags resend rather than
being deduped away, and each route authenticates as the account that can see its target.
heartbeat.sh's own session_id-matching behaviour, and the launchers that make it possible,
are tests/test_alert_watcher_session.py — this file keeps only the routing."""

from __future__ import annotations

import os
import pathlib
import shutil
import time
import unittest

from test_alert_watcher import Rig

EXPECTED_TESTS = 9


def age(path: pathlib.Path, minutes: int) -> None:
    then = time.time() - minutes * 60
    os.utime(path, (then, then))


class HeartbeatRoutingTest(Rig):
    def claude_faithful_any_target(self, rc: int = 0):
        """Like Rig.claude_faithful, but sends to whichever session the
        prompt names, since the target can now be WATCHER or WATCHER-STANDIN."""
        helper = self.camp / "faithful_any.py"
        helper.write_text(
            "import json, re, sys\n"
            "text = sys.stdin.read()\n"
            "target = re.search(r'named exactly (\\S+)\\.', text).group(1)\n"
            "body = text.split('---\\n')[1].rsplit('\\n---', 1)[0]\n"
            "send = {'message': {'content': [{'type': 'tool_use', 'id': 't1',\n"
            "        'name': 'SendMessage', 'input': {'to': target, 'message': body}}]}}\n"
            "res = {'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't1',\n"
            "       'content': json.dumps({'success': True})}]}}\n"
            "print(json.dumps(send)); print(json.dumps(res))\n", "utf-8")
        real = shutil.which("python3")
        (self.stub / "claude").write_text(
            f"#!/bin/bash\nenv >> {self.camp}/claude-env.txt\n"
            f"tee {self.camp}/prompt.txt | \"{real}\" {helper}\nexit {rc}\n")
        (self.stub / "claude").chmod(0o755)

    def test_a_fresh_heartbeat_targets_the_watcher(self):
        (self.camp / "WATCHER.heartbeat").write_text("", "utf-8")
        self.claude_faithful_any_target()
        self.assertEqual(0, self.run_alert("  !! red   (since 2026-08-31T10:00+0200)"))
        self.assertIn("delivered to WATCHER (", self.log())

    def test_a_stale_heartbeat_targets_the_stand_in(self):
        hb = self.camp / "WATCHER.heartbeat"
        hb.write_text("", "utf-8")
        age(hb, 31)
        self.claude_faithful_any_target()
        self.assertEqual(0, self.run_alert("  !! red   (since 2026-08-31T10:00+0200)"))
        self.assertIn("delivered to WATCHER-STANDIN (", self.log())

    def test_a_target_change_with_identical_flags_still_resends(self):
        # the target is part of the dedupe key: a heartbeat going stale
        # must resend even flags that did not change, not be deduped away
        hb = self.camp / "WATCHER.heartbeat"
        hb.write_text("", "utf-8")          # fresh: targets WATCHER
        self.claude_faithful_any_target()
        line = "  !! red   (since 2026-08-31T10:00+0200)"
        self.assertEqual(0, self.run_alert(line))
        self.assertIn("delivered to WATCHER (", self.log())
        self.assertEqual(1, self.log().count("delivered to"))

        age(hb, 31)                          # now stale: same flags, new target
        self.assertEqual(0, self.run_alert(line))
        self.assertIn("delivered to WATCHER-STANDIN (", self.log())
        self.assertEqual(2, self.log().count("delivered to"))
        self.assertNotIn("flags unchanged, not re-sent", self.log())

    def test_the_watcher_route_uses_its_own_account_not_the_ambient_one(self):
        (self.camp / "WATCHER.heartbeat").write_text("", "utf-8")   # fresh -> WATCHER
        self.claude_faithful_any_target()
        self.assertEqual(0, self.run_alert(
            "  !! red   (since 2026-08-31T10:00+0200)",
            extra_env={"CLAUDE_CONFIG_DIR": "/cfg/work"}))
        env_text = (self.camp / "claude-env.txt").read_text("utf-8")
        self.assertIn("DRIVE_MESSENGER=1", env_text)
        self.assertIn("CLAUDE_CONFIG_DIR=/cfg/second", env_text)

    def test_the_stand_in_route_never_leaks_the_primary_account(self):
        hb = self.camp / "WATCHER.heartbeat"
        hb.write_text("", "utf-8")
        age(hb, 31)                                                  # stale -> WATCHER-STANDIN
        self.claude_faithful_any_target()
        self.assertEqual(0, self.run_alert(
            "  !! red   (since 2026-08-31T10:00+0200)",
            extra_env={"CLAUDE_CONFIG_DIR": "/cfg/second"}))
        env_text = (self.camp / "claude-env.txt").read_text("utf-8")
        self.assertIn("DRIVE_MESSENGER=1", env_text)
        self.assertNotIn("CLAUDE_CONFIG_DIR=", env_text)


class RelayNameTest(Rig):
    """A live campaign can have two sessions sharing the bare name WATCHER
    (a stale background shell and the interactive one): alert-watcher.sh
    must target the launcher's own unique relay name (<target>.name), never
    the bare one, falling back to the bare name only when no file exists."""

    def test_the_bare_names_bracket_id_is_not_proven_once_a_name_file_exists(self):
        (self.camp / "WATCHER.heartbeat").write_text("", "utf-8")   # fresh -> WATCHER
        (self.camp / "WATCHER.name").write_text("WATCHER-9a8a9f01", "utf-8")
        self.claude_faithful(to="WATCHER [b362c3]")                 # some OTHER WATCHER session
        self.assertEqual(1, self.run_alert("  !! red   (since 2026-08-31T10:00+0200)"))
        self.assertNotIn("delivered to WATCHER", self.log())

    def test_the_exact_unique_name_is_proven(self):
        (self.camp / "WATCHER.heartbeat").write_text("", "utf-8")
        (self.camp / "WATCHER.name").write_text("WATCHER-9a8a9f01", "utf-8")
        self.claude_faithful(to="WATCHER-9a8a9f01")
        self.assertEqual(0, self.run_alert("  !! red   (since 2026-08-31T10:00+0200)"))
        self.assertIn("delivered to WATCHER", self.log())
        prompt = (self.camp / "prompt.txt").read_text("utf-8")
        self.assertIn("named exactly WATCHER-9a8a9f01", prompt)

    def test_a_replacement_sessions_new_name_with_unchanged_flags_still_resends(self):
        # a replacement session (WATCHER.name changes) must be treated as
        # news even when the role and flags did not change: the old name's
        # session may no longer be the one watching
        (self.camp / "WATCHER.heartbeat").write_text("", "utf-8")
        (self.camp / "WATCHER.name").write_text("WATCHER-aaaaaaaa", "utf-8")
        self.claude_faithful(to="WATCHER-aaaaaaaa")
        line = "  !! red   (since 2026-08-31T10:00+0200)"
        self.assertEqual(0, self.run_alert(line))
        self.assertEqual(1, self.log().count("delivered to WATCHER"))

        (self.camp / "WATCHER.name").write_text("WATCHER-bbbbbbbb", "utf-8")   # replaced
        self.claude_faithful(to="WATCHER-bbbbbbbb")
        self.assertEqual(0, self.run_alert(line))
        self.assertEqual(2, self.log().count("delivered to WATCHER"))
        self.assertNotIn("flags unchanged, not re-sent", self.log())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
