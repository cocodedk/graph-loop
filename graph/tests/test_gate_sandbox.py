"""A gate is shell a planner may have written, so it does not get the driver's keys.

`replan` rewrites a refused CODE gate, a reviewer reads it, and `run_gate` hands
it to `bash -c`. Model text must not become host authority because another model
approved it. The box is proved before it is trusted; the environment scrub works
either way.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import gate_sandbox
import tmp_root  # noqa: F401 — every temp file of this process under one root, gone at exit
from gates import run_gate

EXPECTED_TESTS = 13


class TheDriversKeysAreNotThere(unittest.TestCase):
    def test_every_credential_shaped_name_is_dropped(self):
        with unittest.mock.patch.dict(os.environ, {
                "CLAUDE_CONFIG_DIR": "/cfg/work", "ANTHROPIC_API_KEY": "sk-x",
                "GH_TOKEN": "t", "AWS_SECRET_ACCESS_KEY": "s", "GRAPH_BACKLOG": "b",
                "SSH_AUTH_SOCK": "/tmp/s", "PATH": "/usr/bin"}):
            env = gate_sandbox.environment("/tmp/home")
        for gone in ("CLAUDE_CONFIG_DIR", "ANTHROPIC_API_KEY", "GH_TOKEN",
                     "AWS_SECRET_ACCESS_KEY", "GRAPH_BACKLOG", "SSH_AUTH_SOCK"):
            self.assertNotIn(gone, env)

    def test_what_a_gate_needs_to_run_is_kept(self):
        with unittest.mock.patch.dict(os.environ, {"PATH": "/usr/bin", "LANG": "C"}):
            env = gate_sandbox.environment("/tmp/home")
        self.assertEqual("/usr/bin", env["PATH"])
        self.assertEqual("C", env["LANG"])

    def test_user_site_packages_survive_the_home_swap(self):
        # Replacing HOME alone severed pip --user packages: uvicorn died
        # silently and T25 lost three rounds. The user-site is code, not a
        # credential; a pre-set PYTHONUSERBASE is preserved, so the host env
        # is cleared for a deterministic assertion.
        import unittest.mock
        with unittest.mock.patch.dict("os.environ", {"HOME": "/tmp/real-home"}, clear=True):
            env = gate_sandbox.environment("/tmp/empty-home")
        self.assertEqual("/tmp/real-home/.local", env["PYTHONUSERBASE"])
        self.assertEqual("/tmp/empty-home", env["HOME"])

    def test_the_home_it_is_given_is_the_one_it_gets(self):
        self.assertEqual("/tmp/home", gate_sandbox.environment("/tmp/home")["HOME"])

    def test_a_real_gate_cannot_read_the_config_directory_from_its_environment(self):
        out = run_gate("env | grep -c CLAUDE || true", tempfile.mkdtemp())
        self.assertEqual("0", out.output.strip())


class TheBoxIsProvedBeforeItIsTrusted(unittest.TestCase):
    def test_without_bubblewrap_there_is_no_box_and_the_gate_still_runs(self):
        with unittest.mock.patch.object(gate_sandbox, "BWRAP", None), \
             unittest.mock.patch.object(gate_sandbox, "_WORKS", None):
            self.assertFalse(gate_sandbox.works())
            self.assertEqual(["bash", "-c", "true"], gate_sandbox.argv("true", "/tmp", "/tmp"))

    def test_the_box_binds_the_worktree_writable_and_the_rest_read_only(self):
        with unittest.mock.patch.object(gate_sandbox, "BWRAP", "/usr/bin/bwrap"):
            line = " ".join(gate_sandbox.argv("true", "/tmp", "/tmp/home"))
        self.assertIn("--ro-bind / /", line)
        self.assertIn("--bind /tmp /tmp", line)
        self.assertIn("--bind /tmp/home /tmp/home", line)

    def test_the_real_home_and_the_docker_socket_are_masked_not_read_only(self):
        with unittest.mock.patch.object(gate_sandbox, "BWRAP", "/usr/bin/bwrap"), \
             unittest.mock.patch.object(gate_sandbox, "MASKED",
                                        (os.path.expanduser("~"), "/tmp")):
            line = " ".join(gate_sandbox.argv("true", "/tmp", "/tmp/home"))
        self.assertIn(f"--tmpfs {os.path.expanduser('~')}", line)
        # read-only was never enough: reading a credential is spending it
        self.assertNotIn(f"--ro-bind {os.path.expanduser('~')}", line)

    def test_a_path_that_is_not_there_is_not_masked_into_existence(self):
        with unittest.mock.patch.object(gate_sandbox, "BWRAP", "/usr/bin/bwrap"), \
             unittest.mock.patch.object(gate_sandbox, "MASKED", ("/no/such/path",)):
            self.assertNotIn("/no/such/path",
                             " ".join(gate_sandbox.argv("true", "/tmp", "/tmp/home")))

    def test_a_non_directory_masked_path_is_bound_from_dev_null_not_tmpfs(self):
        # tmpfs mounts only onto a directory; the live docker.sock is a socket,
        # not a directory, and ENOTDIR is what a real box would hit there.
        with tempfile.TemporaryDirectory() as tmp:
            sock_path = os.path.join(tmp, "docker.sock")
            pathlib.Path(sock_path).touch()
            with unittest.mock.patch.object(gate_sandbox, "BWRAP", "/usr/bin/bwrap"), \
                 unittest.mock.patch.object(gate_sandbox, "MASKED", (sock_path, tmp)):
                line = " ".join(gate_sandbox.argv("true", "/tmp", "/tmp/home"))
        self.assertIn(f"--ro-bind /dev/null {sock_path}", line)
        self.assertNotIn(f"--tmpfs {sock_path}", line)
        self.assertIn(f"--tmpfs {tmp}", line)

    def test_the_result_says_whether_the_box_held_not_whether_it_was_asked_for(self):
        out = run_gate("true", tempfile.mkdtemp())
        self.assertEqual(gate_sandbox.works(), out.confined)

    def test_a_live_gate_is_never_confined(self):
        seen = {}

        def watch(argv, **kwargs):
            seen["argv"], seen["env"] = argv, kwargs.get("env")
            raise OSError("stop here")

        with unittest.mock.patch("runner.run", watch):
            run_gate("true", tempfile.mkdtemp(), confine=False)
        self.assertEqual(["bash", "-c", "true"], seen["argv"])
        self.assertIsNone(seen["env"])   # the commander's own gate, with the stack it needs


class TheCountIsAsserted(unittest.TestCase):
    def test_this_module_holds_the_tests_it_says_it_does(self):
        found = unittest.defaultTestLoader.loadTestsFromName(__name__).countTestCases()
        self.assertEqual(EXPECTED_TESTS, found)


if __name__ == "__main__":
    unittest.main()
