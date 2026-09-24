"""handoff-standin.sh's own internal behaviour: split out of
test_alert_watcher_session.py at the 200-line fixpoint (CLAUDE.md), which
stays the front door for heartbeat.sh and start-watcher.sh. A failure once
the stand-in's session has actually started must clean up after itself --
the next tick must not mistake a running-but-unbriefed session for ready."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit

GRAPH = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_TESTS = 4


class StandInLauncherTest(unittest.TestCase):
    """handoff-standin.sh cleans up after itself: a failure once the session has
    actually started must not leave a stale WATCHER-STANDIN.session or a
    running-but-unbriefed session for the next tick to mistake for ready."""

    def setUp(self):
        self.camp = pathlib.Path(tempfile.mkdtemp())
        self.stub = pathlib.Path(tempfile.mkdtemp())
        self.state = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.camp, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.stub, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.state, ignore_errors=True)
        # a stateful fake tmux: new-session/kill-session flip one marker
        # file, load-buffer succeeds, paste-buffer is the brief step that
        # fails -- so a session starts, then the brief never lands
        fake = self.stub / "tmux"
        fake.write_text(
            "#!/bin/bash\n"
            'M="$FAKE_TMUX_STATE/up"\n'
            'case "$1" in\n'
            '  has-session) [ -f "$M" ] && exit 0 || exit 1 ;;\n'
            '  new-session) touch "$M"; exit 0 ;;\n'
            '  capture-pane) echo x; exit 0 ;;\n'
            '  load-buffer) exit 0 ;;\n'
            '  paste-buffer) exit 1 ;;\n'
            '  send-keys) exit 0 ;;\n'
            '  kill-session) rm -f "$M"; exit 0 ;;\n'
            '  *) exit 1 ;;\n'
            'esac\n')
        fake.chmod(0o755)

    def run_handoff(self, dry: bool = False):
        env = dict(os.environ, GRAPH_CAMPAIGN=str(self.camp),
                   PATH=f"{self.stub}:{os.environ['PATH']}",
                   FAKE_TMUX_STATE=str(self.state), GRAPH_BRANCH="campaign/test")
        if dry:
            env["DRY"] = "1"
        return subprocess.run(["bash", str(GRAPH / "handoff-standin.sh")], env=env,
                              check=False, capture_output=True, text=True)

    def test_a_failed_brief_step_cleans_up_the_session_and_its_record(self):
        result = self.run_handoff()
        self.assertEqual(1, result.returncode)
        self.assertFalse((self.camp / "WATCHER-STANDIN.session").exists())
        self.assertFalse((self.state / "up").exists())          # the fake session was killed

    def test_the_next_call_starts_fresh_after_a_cleaned_up_failure(self):
        self.run_handoff()
        second = self.run_handoff()
        # proves it reached the brief step again, not a short-circuit "already up"
        self.assertIn("pasting the standing brief failed", second.stdout)

    def test_dry_mode_previews_a_unique_relay_name(self):
        # two live sessions can share the bare WATCHER-STANDIN name; only a
        # unique one lets alert-watcher.sh bind delivery to this launch
        result = self.run_handoff(dry=True)
        self.assertRegex(result.stdout, r"--remote-control WATCHER-STANDIN-[0-9a-f]{8}\b")


class CountTest(unittest.TestCase):
    def test_the_suite_asserts_its_own_size(self):
        found = unittest.TestLoader().discover(
            str(pathlib.Path(__file__).parent), pattern=pathlib.Path(__file__).name)
        self.assertEqual(EXPECTED_TESTS, found.countTestCases())


if __name__ == "__main__":
    unittest.main()
