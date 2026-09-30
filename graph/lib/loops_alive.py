"""Proof that a running build is making progress: how long ago its transcript last grew and how many steps
it holds. The loop's own log is silent until a call ends, so this reads the builder's session file."""

from __future__ import annotations

import os
import re

from loops_list import duration
from screen_color import paint, quiet


def children(pid: int, proc: str) -> list[int]:
    """Every process below `pid`, read from `<proc>/<n>/stat` (`pid (name) state ppid ...`)."""
    parent: dict[int, list[int]] = {}
    for name in os.listdir(proc):
        if not name.isdigit():
            continue
        try:
            with open(os.path.join(proc, name, "stat"), encoding="utf-8", errors="replace") as stat:
                ppid = int(stat.read().rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
        parent.setdefault(ppid, []).append(int(name))
    found, todo = [], [pid]
    while todo:
        for child in parent.get(todo.pop(), []):
            found.append(child)
            todo.append(child)
    return found


def config_of(pid: int, proc: str) -> str:
    """The process's CLAUDE_CONFIG_DIR, the default one when it has none."""
    try:
        with open(os.path.join(proc, str(pid), "environ"), "rb") as env:
            for word in env.read().split(b"\0"):
                if word.startswith(b"CLAUDE_CONFIG_DIR="):
                    return os.fsdecode(word[18:])
    except OSError:
        pass
    return os.path.join(os.path.expanduser("~"), ".claude")


def progress(pid: int, now: float, proc: str = "/proc", color: bool = False) -> str:
    """`last step 12s ago · 186 steps` from the newest session file of a process below `pid`, "" when
    there is none; with `color` the `last step … ago` is yellow from 5 minutes, red from 15. ponytail: Linux /proc only, and a working directory whose encoded name is over 200
    characters is hashed by Claude, so its file is missed."""
    best: tuple[float, str] | None = None
    try:
        kids = children(pid, proc)
    except OSError:
        return ""
    for kid in kids:
        try:
            folder = os.path.join(config_of(kid, proc), "projects", re.sub(r"[^A-Za-z0-9]", "-", os.readlink(os.path.join(proc, str(kid), "cwd"))))
            files = [os.path.join(folder, name) for name in os.listdir(folder) if name.endswith(".jsonl")]
        except OSError:
            continue
        for path in files:
            try:
                best = max(best or (0.0, ""), (os.path.getmtime(path), path))
            except OSError:
                continue
    if best is None:
        return ""
    with open(best[1], encoding="utf-8", errors="replace") as session:
        steps = sum('"type":"assistant"' in line for line in session)
    quiet_for = max(0, int(now - best[0]))
    return f"{paint(f'last step {duration(quiet_for)} ago', quiet(quiet_for), color)} · {steps} steps"
