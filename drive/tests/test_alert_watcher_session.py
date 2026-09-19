"""heartbeat.sh's own unit behaviour, and the launchers that make its
session_id match possible — split out of test_alert_watcher_heartbeat.py at
the 200-line fixpoint (CLAUDE.md); that file keeps the routing tests. Only a
stdin session_id matching a recorded .session file earns a touch, never an
inherited WATCHER_ROLE (any child claude process gets one); start-watcher.sh
is the only tracked launcher that writes WATCHER.session, and only when one
is not already there."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

DRIVE = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_TESTS = 12



class HeartbeatProducerTest(unittest.TestCase):
    """heartbeat.sh itself: only a session_id matching a recorded .session file earns a touch."""

    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.camp, ignore_errors=True)

    def run_heartbeat(self, config_dir: str, role: str = "", session_id: str = "",
                       messenger: bool = False, cwd: str | None = None) -> int:
        env = dict(os.environ, DRIVE_CAMPAIGN=str(self.camp), CLAUDE_CONFIG_DIR=config_dir)
        env.pop("WATCHER_ROLE", None)
        if role:
            env["WATCHER_ROLE"] = role
        env.pop("DRIVE_MESSENGER", None)
        if messenger:
            env["DRIVE_MESSENGER"] = "1"
        stdin = json.dumps({"session_id": session_id, "hook_event_name": "Stop"}) if session_id else ""
        return subprocess.run(["bash", str(DRIVE / "heartbeat.sh")], env=env, input=stdin,
                              cwd=cwd, check=False, capture_output=True, text=True).returncode

    def test_an_unknown_session_touches_nothing(self):
        # WATCHER_ROLE is now ignored entirely: a child process inherits it,
        # so only a session_id match may ever earn a touch
        self.assertEqual(0, self.run_heartbeat("/cfg/second", role="primary"))
        self.assertFalse((self.camp / "WATCHER.heartbeat").exists())
        self.assertFalse((self.camp / "WATCHER-STANDIN.heartbeat").exists())

    def test_the_recorded_session_id_touches_watchers_own_heartbeat(self):
        (self.camp / "WATCHER.session").write_text("abc-123", "utf-8")
        self.assertEqual(0, self.run_heartbeat("/cfg/work", session_id="abc-123"))
        self.assertTrue((self.camp / "WATCHER.heartbeat").exists())
        self.assertFalse((self.camp / "WATCHER-STANDIN.heartbeat").exists())

    def test_a_different_session_id_touches_nothing(self):
        (self.camp / "WATCHER.session").write_text("abc-123", "utf-8")
        self.assertEqual(0, self.run_heartbeat("/cfg/work", session_id="someone-else"))
        self.assertFalse((self.camp / "WATCHER.heartbeat").exists())
        self.assertFalse((self.camp / "WATCHER-STANDIN.heartbeat").exists())

    def test_a_session_id_matching_the_stand_ins_file_touches_its_heartbeat(self):
        (self.camp / "WATCHER-STANDIN.session").write_text("xyz-789", "utf-8")
        self.assertEqual(0, self.run_heartbeat("/cfg/second", session_id="xyz-789"))
        self.assertTrue((self.camp / "WATCHER-STANDIN.heartbeat").exists())
        self.assertFalse((self.camp / "WATCHER.heartbeat").exists())

    def test_the_messengers_own_call_never_touches_a_heartbeat(self):
        # the messenger's own sub-call must never touch a heartbeat, role or not
        self.assertEqual(0, self.run_heartbeat("/cfg/second",
                                                role="primary", messenger=True))
        self.assertFalse((self.camp / "WATCHER.heartbeat").exists())
        self.assertFalse((self.camp / "WATCHER-STANDIN.heartbeat").exists())

    def test_a_restarted_session_with_no_recorded_file_touches_nothing(self):
        self.assertEqual(0, self.run_heartbeat("/cfg/work", session_id="someone-else"))
        self.assertFalse((self.camp / "WATCHER.heartbeat").exists())
        self.assertFalse((self.camp / "WATCHER-STANDIN.heartbeat").exists())

    def test_an_absolute_path_invocation_works_from_another_cwd(self):
        (self.camp / "WATCHER.session").write_text("abc-123", "utf-8")
        self.assertEqual(0, self.run_heartbeat("/cfg/work", session_id="abc-123", cwd="/tmp"))
        self.assertTrue((self.camp / "WATCHER.heartbeat").exists())


class DryRunTest(unittest.TestCase):
    """start-watcher.sh's DRY mode previews the exact claude invocation
    without starting anything -- the only way to prove, without a live
    session, which flag carries the session_id heartbeat.sh's hook will see."""

    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.stub = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.camp, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.stub, ignore_errors=True)
        # a harmless stand-in for claude: keeps this test safe even before
        # DRY mode exists, when the script would otherwise exec it for real
        fake = self.stub / "claude"
        fake.write_text("#!/bin/bash\necho \"claude $*\"\n")
        fake.chmod(0o755)

    def dry(self, extra_env: dict | None = None) -> str:
        env = dict(os.environ, DRIVE_CAMPAIGN=str(self.camp), DRY="1",
                   PATH=f"{self.stub}:{os.environ['PATH']}")
        if extra_env:
            env.update(extra_env)
        return subprocess.run(["bash", str(DRIVE / "start-watcher.sh")], env=env,
                              check=False, capture_output=True, text=True).stdout

    def test_a_fresh_campaign_previews_a_fresh_session_id(self):
        out = self.dry()
        self.assertIn("--session-id", out)
        self.assertNotIn("--resume", out)
        self.assertFalse((self.camp / "WATCHER.session").exists())   # DRY starts nothing

    def test_an_existing_session_is_previewed_as_a_resume_of_its_stored_id(self):
        (self.camp / "WATCHER.session").write_text("existing-id-123", "utf-8")
        out = self.dry()
        self.assertIn("--resume existing-id-123", out)
        self.assertNotIn("--session-id", out)

    def test_a_custom_config_dir_is_previewed(self):
        out = self.dry(extra_env={"WATCHER_CONFIG_DIR": "/tmp/custom-dir"})
        self.assertIn("CLAUDE_CONFIG_DIR=/tmp/custom-dir", out)

    def test_any_argument_at_all_is_rejected(self):
        # a deny-list of flags is the wrong shape (CLAUDE.md: a parameter
        # that can name another identity is the capability, not the guard
        # -- delete it rather than check it): the script takes NO
        # arguments, so any argument at all -- whatever form it takes -- is
        # rejected the same way
        env = dict(os.environ, DRIVE_CAMPAIGN=str(self.camp), DRY="1",
                   PATH=f"{self.stub}:{os.environ['PATH']}")
        message = ("start-watcher.sh takes no arguments: the campaign's "
                   "WATCHER.session and WATCHER.name own the identity")
        for args in (["--resume", "x"], ["-rabc"], ["--name", "x"]):
            with self.subTest(args=args):
                result = subprocess.run(["bash", str(DRIVE / "start-watcher.sh"), *args],
                                        env=env, check=False, capture_output=True, text=True)
                self.assertEqual(2, result.returncode)
                self.assertIn(message, result.stderr)


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
