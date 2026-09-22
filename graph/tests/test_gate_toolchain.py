"""A fresh machine's home toolchain reaches a gate without exposing its keys."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import gate_sandbox


class ToolchainAccess(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = self.root / "host"
        self.home = self.root / "gate"
        self.home.mkdir()
        self.sdk = self.host / "Android/Sdk"
        self.sdk.mkdir(parents=True)
        self.jdk = self.host / "jdks/17"
        (self.jdk / "bin").mkdir(parents=True)
        (self.jdk / "bin/javac").touch()
        self.gradle = self.host / ".gradle"
        self.gradle.mkdir()
        (self.gradle / "gradle.properties").write_text(
            f"org.gradle.java.home={self.jdk}\npassword=hidden\n")
        dist = self.gradle / "wrapper/dists/gradle-test"
        dist.mkdir(parents=True)
        (dist / "distribution").write_text("cached")
        (self.host / "credential").write_text("hidden")
        (dist / "credential-link").symlink_to(self.host / "credential")
        self.env = patch.dict(os.environ, {"HOME": str(self.host), "PATH": "/usr/bin"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_no_exports_discovers_sdk_compiler_and_reuses_distribution(self):
        env = gate_sandbox.environment(str(self.home))
        self.assertEqual(str(self.sdk), env.get("ANDROID_HOME"))
        self.assertEqual(str(self.jdk), env.get("JAVA_HOME"))
        cache = Path(env["GRADLE_USER_HOME"])
        self.assertEqual(self.home / ".gradle", cache)
        copied = cache / "wrapper/dists/gradle-test/distribution"
        self.assertEqual("cached", copied.read_text())
        copied.write_text("gate can write")
        self.assertEqual("cached", (self.gradle / "wrapper/dists/gradle-test/distribution").read_text())
        self.assertFalse((cache / "gradle.properties").exists())
        self.assertFalse((cache / "wrapper/dists/gradle-test/credential-link").exists())
        self.assertEqual(str(self.jdk / "bin"), env["PATH"].split(os.pathsep)[0])

    def test_tools_are_restored_read_only_after_the_home_mask(self):
        with patch.object(gate_sandbox, "BWRAP", "bwrap"), \
             patch.object(gate_sandbox, "MASKED", (str(self.host),)):
            args = gate_sandbox.argv("true", str(self.root), str(self.home))
        mask = args.index("--tmpfs")
        for tool in (self.sdk, self.jdk):
            index = args.index(str(tool))
            self.assertGreater(index, mask)
            self.assertEqual(["--ro-bind", str(tool), str(tool)], args[index - 1:index + 2])
        self.assertNotIn(str(self.gradle), args)
        self.assertNotIn(str(self.host / "credential"), args)

    def test_explicit_locations_and_symlinks_use_reachable_canonical_paths(self):
        sdk = self.root / "custom-sdk"
        sdk.mkdir()
        link = self.host / "sdk-link"
        link.symlink_to(sdk, target_is_directory=True)
        with patch.dict(os.environ, {"ANDROID_HOME": str(link),
                                    "GRADLE_USER_HOME": str(self.gradle)}):
            env = gate_sandbox.environment(str(self.home))
        self.assertEqual(str(sdk), env["ANDROID_HOME"])
        self.assertEqual(str(sdk), env["ANDROID_SDK_ROOT"])
        self.assertNotEqual(str(self.gradle), env["GRADLE_USER_HOME"])

    def test_a_shell_gate_uses_the_discovered_compiler_and_private_cache(self):
        compiler = self.jdk / "bin/javac"
        compiler.write_text("#!/bin/sh\nprintf 'compiler-ready'\n")
        compiler.chmod(0o755)
        env = gate_sandbox.environment(str(self.home))
        result = subprocess.run(
            ["/bin/bash", "-c", ('javac && test -d "$ANDROID_HOME" && '
             'test -f "$GRADLE_USER_HOME/wrapper/dists/gradle-test/distribution" && '
             'test ! -e "$GRADLE_USER_HOME/gradle.properties"')],
            env=env, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("compiler-ready", result.stdout)

    def test_a_jre_is_not_selected_as_the_compiler(self):
        (self.gradle / "gradle.properties").unlink()
        with patch.dict(os.environ, {"JAVA_HOME": str(self.host / "jre")}), \
             patch("shutil.which", return_value=str(self.jdk / "bin/javac")):
            env = gate_sandbox.environment(str(self.home))
        self.assertEqual(str(self.jdk), env["JAVA_HOME"])


if __name__ == "__main__":
    unittest.main()
