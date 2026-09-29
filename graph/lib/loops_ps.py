"""Which processes are running lean loops: read from `ps`, judged by their command line."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from typing import NamedTuple

FLAGS = ("--workspace", "--repo", "--spec")


class PsError(Exception):
    """`ps` could not be run, or said it failed."""


class Loop(NamedTuple):
    pid: int
    age: int                 # seconds since the process started
    project: str             # the last part of --repo, `?` when it cannot be resolved
    spec: str                # --spec's file name without `.md`
    workspace: str | None    # None when it cannot be resolved


def read_ps() -> str:
    try:
        done = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True, check=False)
    except OSError as error:
        raise PsError(str(error)) from error
    if done.returncode:
        raise PsError(done.stderr.strip() or f"ps exited {done.returncode}")
    return done.stdout


def cwd_of(pid: int) -> str | None:
    # ponytail: /proc is Linux only; on macOS ask `lsof -a -d cwd -Fn -p <pid>` instead
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


def flag_values(words: list[str]) -> dict[str, str] | None:
    """The values of the three flags, or None when the words do not give all three.
    A value runs to the next `--` word, so a path with spaces in it stays whole."""
    found: dict[str, str] = {}
    at = 0
    while at < len(words):
        flag, equals, first = words[at].partition("=")
        at += 1
        if flag not in FLAGS:
            continue
        parts = [first] if equals else []
        while at < len(words) and not words[at].startswith("--"):
            parts.append(words[at])
            at += 1
        if " ".join(parts):
            found.setdefault(flag, " ".join(parts))
    return found if len(found) == len(FLAGS) else None


def lean_flags(args: str) -> dict[str, str] | None:
    """The flags of a Python interpreter running `lean.py`; None for anything else."""
    # ponytail: ps flattens the arguments, so runs of spaces collapse and an interpreter path with a
    # space in it is missed; /proc/<pid>/cmdline keeps the words apart if that ever matters
    words = args.split()
    if not words or not os.path.basename(words[0]).startswith("python"):
        return None
    at = 1
    while at < len(words) and words[at].startswith("-"):   # interpreter options: -X dev, -u, -W ignore
        if words[at] in ("-c", "-m"):
            return None                                     # code or a module, not a script
        at += 2 if words[at] in ("-W", "-X") else 1
    start = at
    while at < len(words) and not words[at].startswith("--"):
        at += 1
    script = " ".join(words[start:at])
    if script != "lean.py" and not script.endswith("/lean.py"):
        return None
    return flag_values(words[at:])


def resolve(path: str, cwd: str | None) -> str | None:
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(cwd, path)) if cwd else None


def loops_in(ps_text: str, cwd_for: Callable[[int], str | None] = cwd_of) -> list[Loop]:
    """The running lean loops in `ps -eo pid,etimes,args` output, lowest process id first."""
    found = []
    for line in ps_text.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3 or not (parts[0].isdigit() and parts[1].isdigit()):
            continue                                   # the header, or a process with no arguments
        flags = lean_flags(parts[2])
        if flags is None:
            continue
        pid = int(parts[0])
        cwd = cwd_for(pid)
        repo = resolve(flags["--repo"], cwd)
        project = os.path.basename(repo) if repo else "?"
        spec = os.path.basename(flags["--spec"]).removesuffix(".md")
        found.append(Loop(pid, int(parts[1]), project, spec, resolve(flags["--workspace"], cwd)))
    return sorted(found)
