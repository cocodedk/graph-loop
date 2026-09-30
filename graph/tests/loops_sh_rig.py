"""What the tests of graph/loops.sh share: a fake command, a fake `clear` and `ps`, and how to run it."""

import os
import pathlib
import signal
import subprocess
import tempfile
import time
import unittest

GRAPH = pathlib.Path(__file__).resolve().parents[1]
CLEAR = "<CLEAR>"
FAILED = "cannot read the process list"
# A stand-in for loops.py: it logs what it is asked and what it could read from standard input,
# answers --path from a file and --screen with its own arguments; FAKE_STATUS makes it fail and
# FAKE_GATE makes a --screen wait until the test creates the file `go`.
FAKE = f"""#!/bin/sh
echo "$*" >> "$FAKE_DIR/calls"
cat >> "$FAKE_DIR/stdin"
if [ -n "$FAKE_GATE" ] && [ "$1" = "--screen" ]; then
  touch "$FAKE_DIR/started"
  while [ ! -f "$FAKE_DIR/go" ]; do sleep 0.05; done
fi
if [ -n "$FAKE_STATUS" ]; then echo "{FAILED}"; exit "$FAKE_STATUS"; fi
case "$1" in
  --path) cat "$FAKE_DIR/path-$2" 2>/dev/null; exit 0 ;;
esac
echo "SCREEN $*"
"""


# A stand-in for `tput lines`: each call prints the next height of the file `rows` (the last one
# repeats), and nothing when the file is empty; any other question is answered with silence.
TPUT = """#!/bin/sh
[ "$1" = lines ] && [ -s "$FAKE_DIR/rows" ] || exit 0
head -n 1 "$FAKE_DIR/rows"
if [ "$(wc -l < "$FAKE_DIR/rows")" -gt 1 ]; then
  tail -n +2 "$FAKE_DIR/rows" > "$FAKE_DIR/rows.next" && mv "$FAKE_DIR/rows.next" "$FAKE_DIR/rows"
fi
exit 0
"""


class Rig(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.here = pathlib.Path(tempfile.mkdtemp())     # where the script runs: it must stay empty
        for name, body in (("fake", FAKE), ("clear", f"#!/bin/sh\necho '{CLEAR}'\n"),
                           ("tput", TPUT),
                           ("ps", "#!/bin/sh\ncat \"$FAKE_DIR/ps.out\"\n")):
            (self.dir / name).write_text(body)
            (self.dir / name).chmod(0o755)

    def path(self, number, folder):
        (self.dir / f"path-{number}").write_text(folder)

    def calls(self):
        return (self.dir / "calls").read_text().splitlines()

    def env(self, refresh, status="", fake=True, ps="", gate="", rows=""):
        """The environment of a run; a fake `clear` prints CLEAR, a fake `ps` lists `ps`, a fake
        `tput lines` prints the words of `rows` one per call (nothing when empty)."""
        env = {**os.environ, "PATH": f"{self.dir}{os.pathsep}{os.environ['PATH']}", "FAKE_DIR": str(self.dir),
               "FAKE_STATUS": status, "FAKE_GATE": gate, "LOOPS_REFRESH": refresh}
        (self.dir / "rows").write_text("".join(f"{height}\n" for height in rows.split()))
        env.pop("LOOPS_CMD", None)
        if fake:
            env["LOOPS_CMD"] = str(self.dir / "fake")
        (self.dir / "ps.out").write_text("    PID ELAPSED COMMAND\n" + ps)
        for log in ("calls", "stdin", "started", "go"):
            (self.dir / log).unlink(missing_ok=True)
        return env

    def sh(self, *args, keys="", refresh="0.2", script=None, **more):
        """Run loops.sh with `keys` on standard input until it ends."""
        return subprocess.run(["bash", str(script or GRAPH / "loops.sh"), *args], input=keys,
                              env=self.env(refresh, **more), cwd=self.here, timeout=60,
                              capture_output=True, text=True, check=False)

    def live(self, *args, gate=""):
        """A running loops.sh whose standard input stays open, so the test can press keys; 30s refresh."""
        # A suite started as a background job inherits an ignored SIGINT, and bash cannot trap what it
        # inherits ignored: the script would stop on the end of input, without Ctrl-C's newline.
        return subprocess.Popen(["bash", str(GRAPH / "loops.sh"), *args], env=self.env("30", gate=gate),
                                cwd=self.here, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))

    def wait_for(self, name):
        for _ in range(400):
            if (self.dir / name).exists():
                return
            time.sleep(0.05)
        self.fail(f"{name} never appeared")

    def screens(self, done):
        """The screens a live run printed, each as its lines, and it ended with `stopped watching.`"""
        *shown, last = [text.splitlines() for text in done.stdout.split(CLEAR + "\n")[1:]]
        self.assertEqual("stopped watching.", last.pop())
        return [*shown, last]

    def filters(self):
        """The --only of each screen the fake was asked for; `-` for none."""
        return [line.split("--only ")[1].split()[0] if "--only" in line else "-"
                for line in self.calls() if line.startswith("--screen")]
