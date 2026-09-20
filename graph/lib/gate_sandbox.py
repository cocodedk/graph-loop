"""The box a gate runs in.

A gate is a shell command, and a planner may write one: `replan` rewrites a
refused CODE gate, a reviewer reads it, and then `run_gate` hands it to
`bash -c` in the driver's own process — the whole filesystem, the driver's
credentials, the Docker socket. Model text must not become host authority
because another model approved it, so the command runs confined.

What the box does:
  * only the worktree and /tmp may be written; everything else is read-only,
  * the driver's real home is MASKED, not merely unset: read-only was never
    enough, because reading the agent's own configuration or its ssh keys is
    all it takes to spend them,
  * the sockets that are authority in themselves — Docker above all — are
    masked too, for the same reason,
  * the host's secrets are dropped from the environment.

What it deliberately does NOT do: it keeps the network, because three code
gates install their packages with `npm ci` and blocking it would refuse them
for the environment's shape rather than the task's work. A gate can therefore
still read the repository and reach out; closing that needs a per-card
declaration, and it is not this brick.

A LIVE gate is never confined: it performs the work it measures, needs Docker
and the database, and is the commander's own text — never a planner's.

The box is PROVED before it is trusted. On this host bubblewrap cannot map uids
("Permission denied") and `systemd-run --user` accepts ProtectHome and ignores
it — a sandbox that silently does nothing is worse than none, because everyone
downstream believes it. So `works()` runs a probe once and the loop reports
what it actually got: with a box, everything below; without one, the environment
scrub alone, which still takes the driver's credentials off the table.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile

BWRAP = shutil.which("bwrap")
# Names that carry a credential or point at one. Dropped whole, by prefix.
SECRET_PREFIXES = ("CLAUDE", "ANTHROPIC", "GRAPH_", "OPENAI", "GH_", "GITHUB",
                   "AWS_", "AZURE", "GOOGLE", "SSH_", "GPG_", "NPM_TOKEN",
                   "DOCKER_", "CODEX")
# Paths that are authority in themselves. Read-only is not enough for any of
# them: reading a credential is spending it, and a socket answers whoever asks.
MASKED = (os.path.expanduser("~"), "/run/docker.sock", "/var/run/docker.sock",
          "/run/user", "/var/run/secrets")


def environment(home: str) -> dict[str, str]:
    """The environment a gate gets: this one, minus every host credential,
    pointed at the empty home the box gives it.

    PYTHONUSERBASE still names the real user-site: replacing HOME alone
    severed pip --user packages (uvicorn first — T25 lost three rounds, and
    three queued gates shared the flaw). This restores such gates only on the
    UNBOXED fallback this host runs: a working box masks ~ wholesale, so a
    boxed gate still needs the worktree venv. Package code is not a
    credential; the secret-named variables stay dropped."""
    out = {name: value for name, value in os.environ.items()
           if not name.startswith(SECRET_PREFIXES)}
    out["HOME"] = home
    # a gate's scratch (the suites leave ~190 test worktrees per run) lands in
    # the home run_gate removes, not in the host's /tmp, which filled on
    # 2026-09-03 and killed every process on the host
    out["TMPDIR"] = home
    out.setdefault("PYTHONUSERBASE", os.path.expanduser("~/.local"))
    return out


def argv(command: str, cwd: str, home: str) -> list[str]:
    """The command line that runs `command` in the box, or plainly if this
    machine has no bubblewrap — said out loud rather than pretended."""
    if not BWRAP:
        return ["bash", "-c", command]
    tree = str(pathlib.Path(cwd).resolve())
    line = [BWRAP, "--die-with-parent", "--unshare-pid",
            "--ro-bind", "/", "/",
            "--proc", "/proc", "--dev", "/dev"]
    for masked in MASKED:
        # Empty, not absent: a path that is simply missing changes what a gate
        # can see, and a path that is read-only is still a credential to read.
        if not pathlib.Path(masked).exists():
            continue
        # A tmpfs mounts only onto a directory (ENOTDIR on the live docker.sock,
        # a socket); a non-directory gets /dev/null bound over it instead, a
        # file over a file. Decided by os.path.isdir on this host — a path that
        # is not here is never masked (above), so its name never has to decide.
        if os.path.isdir(masked):
            line += ["--tmpfs", masked]
        else:
            line += ["--ro-bind", "/dev/null", masked]
    line += ["--bind", tree, tree,          # the work, writable
             "--bind", "/tmp", "/tmp",      # where tests put their scratch
             "--bind", home, home,          # a home with nothing in it
             "--chdir", tree,
             "bash", "-c", command]
    return line


_WORKS: bool | None = None


def works() -> bool:
    """Whether this machine can actually box a gate — asked of the machine, not
    of the binary being present. Answered once, then remembered.

    A false answer is a fact to report on the board, never a silent fallback:
    the gate still runs, with its environment scrubbed, and the reader is told
    the filesystem was not confined.
    """
    global _WORKS
    if _WORKS is None:
        _WORKS = False
        if BWRAP:
            probe = subprocess.run(
                argv("test -w / && exit 1; exit 0", tempfile.gettempdir(),
                     tempfile.gettempdir()),
                capture_output=True, text=True, timeout=30, check=False)
            _WORKS = probe.returncode == 0
    return _WORKS
