"""A running build's proof of progress: its transcript's last change and steps, from a fake /proc."""

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import loops_alive
import tmp_root  # noqa: F401

NOW = 1_000_000


class Alive(unittest.TestCase):
    def setUp(self):
        self.base = pathlib.Path(tempfile.mkdtemp())
        self.proc, self.config, self.tree = self.base / "proc", self.base / "cfg", self.base / "work_tree"
        for path in (self.proc, self.tree):
            path.mkdir()
        self.process(100, 1, self.base)                       # the loop
        self.process(200, 100, self.tree, config=self.config)  # its builder
        folder = self.config / "projects" / loops_alive.re.sub(r"[^A-Za-z0-9]", "-", str(self.tree))
        folder.mkdir(parents=True)
        self.session = folder / "s.jsonl"

    def process(self, pid, ppid, cwd, config=None):
        home = self.proc / str(pid)
        home.mkdir()
        (home / "stat").write_text(f"{pid} (a b) S {ppid} 1 1")
        os.symlink(cwd, home / "cwd")
        (home / "environ").write_bytes(b"A=1\0" + (f"CLAUDE_CONFIG_DIR={config}\0".encode() if config else b""))

    def write(self, steps, age):
        self.session.write_text('{"type":"user"}\n' + '{"type":"assistant"}\n' * steps)
        os.utime(self.session, (NOW - age, NOW - age))

    def test_the_age_of_the_last_step_and_the_steps_so_far(self):
        self.write(186, 12)
        self.assertEqual("last step 12s ago · 186 steps", loops_alive.progress(100, NOW, str(self.proc)))

    def test_a_silent_builder_shows_a_growing_age(self):
        self.write(3, 605)
        self.assertEqual("last step 10m05s ago · 3 steps", loops_alive.progress(100, NOW, str(self.proc)))

    def test_no_builder_or_no_session_file_shows_nothing(self):
        self.assertEqual("", loops_alive.progress(100, NOW, str(self.proc)))     # no file yet
        self.assertEqual("", loops_alive.progress(200, NOW, str(self.proc)))     # no child
        self.assertEqual("", loops_alive.progress(100, NOW, str(self.base / "gone")))


if __name__ == "__main__":
    unittest.main()
