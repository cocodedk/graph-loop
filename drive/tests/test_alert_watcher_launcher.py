"""start-watcher.sh's own argv wiring: split out of
test_alert_watcher_session.py at the 200-line fixpoint (CLAUDE.md), which
stays the front door for heartbeat.sh and DRY mode. The fake claude parses
its OWN argv for --session-id/--resume and feeds THAT id to heartbeat.sh --
reading WATCHER.session off disk instead would hide a launcher that passed
the wrong id."""

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

EXPECTED_TESTS = 5


class PrimaryLauncherTest(unittest.TestCase):
    """start-watcher.sh is the only tracked launcher that writes
    WATCHER.session — an existing one is left alone. The fake claude parses
    its OWN argv for --session-id/--resume and feeds THAT id to heartbeat.sh
    -- reading WATCHER.session off disk instead would hide a launcher that
    passed the wrong id."""

    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.stub = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.camp, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.stub, ignore_errors=True)
        self.argv_file = self.camp / "claude-argv.json"
        self.fake = self.camp / "fake_claude.py"
        self.fake.write_text(
            "import json, subprocess, sys\n"
            "argv = sys.argv[1:]\n"
            "open(" + repr(str(self.argv_file)) + ", 'w').write(json.dumps(argv))\n"
            "sid = ''\n"
            "for i, a in enumerate(argv):\n"
            "    if a in ('--session-id', '--resume') and i + 1 < len(argv):\n"
            "        sid = argv[i + 1]\n"
            "subprocess.run(['bash', " + repr(str(DRIVE / "heartbeat.sh")) + "],\n"
            "                input=json.dumps({'session_id': sid, 'hook_event_name': 'Stop'}),\n"
            "                text=True)\n", "utf-8")
        (self.stub / "claude").write_text(f"#!/bin/bash\npython3 {self.fake} \"$@\"\n")
        (self.stub / "claude").chmod(0o755)

    def _env(self):
        env = dict(os.environ, DRIVE_CAMPAIGN=str(self.camp),
                   PATH=f"{self.stub}:{os.environ['PATH']}")
        env.pop("WATCHER_ROLE", None)
        env.pop("DRIVE_MESSENGER", None)
        return env

    def argv(self) -> list:
        return json.loads(self.argv_file.read_text("utf-8"))

    def test_starting_the_primary_on_a_fresh_campaign_keeps_its_heartbeat_alive(self):
        result = subprocess.run(["bash", str(DRIVE / "start-watcher.sh")], env=self._env(),
                                check=False, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.camp / "WATCHER.heartbeat").exists())
        sid = (self.camp / "WATCHER.session").read_text("utf-8")
        # a unique relay name: two live sessions can share the bare "WATCHER"
        name = (self.camp / "WATCHER.name").read_text("utf-8")
        self.assertEqual(f"WATCHER-{sid[:8]}", name)
        argv = self.argv()
        self.assertEqual(name, argv[argv.index("--remote-control") + 1])

    def test_resuming_an_existing_session_keeps_its_heartbeat_alive(self):
        (self.camp / "WATCHER.session").write_text("already-live-id", "utf-8")
        result = subprocess.run(["bash", str(DRIVE / "start-watcher.sh")], env=self._env(),
                                check=False, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.camp / "WATCHER.heartbeat").exists())

    def test_an_existing_session_file_is_kept_not_overwritten(self):
        (self.camp / "WATCHER.session").write_text("already-live", "utf-8")
        subprocess.run(["bash", str(DRIVE / "start-watcher.sh")], env=self._env(),
                       check=False, capture_output=True, text=True)
        self.assertEqual("already-live", (self.camp / "WATCHER.session").read_text("utf-8"))

    def test_a_wrong_id_from_the_fake_leaves_the_heartbeat_untouched(self):
        # proves the fake is actually sensitive to the id it is given, not
        # a rubber stamp: contrasted against the two tests above, this is
        # the fake+heartbeat.sh pairing's negative case
        (self.camp / "WATCHER.session").write_text("the-real-id", "utf-8")
        subprocess.run(["python3", str(self.fake), "--session-id", "a-wrong-id"],
                       env=self._env(), check=False, capture_output=True, text=True)
        self.assertFalse((self.camp / "WATCHER.heartbeat").exists())


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
