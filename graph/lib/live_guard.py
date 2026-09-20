"""The live builder's fence: a PreToolUse hook on Bash.

Permission rules only ADD to what the settings around a builder already allow,
so a deny list is a chase (absolute paths, wrappers, a later inherited allow).
This hook is a whitelist and it runs first: a Bash command runs only when it
starts with one of this task's commands, at a word boundary, and carries no
shell control character — so nothing can be chained, redirected, substituted
or wrapped. The prefixes come from LIVE_ALLOWED_PREFIXES (one per line), set
by the provider from the task's contract. Exit 2 denies; exit 0 leaves the
decision to the permission rules, which allow exactly the same commands.
"""

from __future__ import annotations

import json
import os
import re
import sys

CONTROL = re.compile(r"[;&|<>`$\n\\]")
ALLOWED_TOOLS = ("Read", "Grep", "Glob", "Edit", "MultiEdit", "Write", "Bash")   # Edit rules bound the writers' paths


def decide(command: str, prefixes: list[str]) -> str:
    """"" when the command may run; otherwise the reason it may not.

    An entry ending in " *" is open: the command may carry arguments after
    it (a verb whose run id is born in the task; cat, ls, head, tail). Any
    other entry is the whole command — "rebuild cli" does not admit
    "rebuild cli broker"."""
    cmd = command.strip()
    if CONTROL.search(cmd):
        return "shell control characters are not allowed in a live task"
    for entry in (p.strip() for p in prefixes):
        if not entry:
            continue
        if entry.endswith(" *"):
            base = entry[:-2]
            if cmd == base or cmd.startswith(base + " "):
                return ""
        elif cmd == entry:
            return ""
    return f"not one of this task's commands: {cmd[:80]}"


WRITERS = ("Edit", "MultiEdit", "Write")


def decide_file(path: str, files: list[str]) -> str:
    """A writer may touch only the task's own files, resolved — an inherited
    broad write rule must not reach the helper or the guard themselves."""
    root = os.environ.get("LIVE_WORKTREE", "")
    try:
        target = os.path.realpath(path)
        inside = os.path.realpath(root) if root else ""
    except (OSError, TypeError, ValueError):
        return "the live guard could not resolve the path"
    if not inside or not (target == inside or target.startswith(inside + os.sep)):
        # the list is data too: an absolute or ../ entry must not whitelist the
        # helper or this guard, so every write stays inside the task's worktree
        return f"not inside this task's worktree: {path[:80]}"
    if target in {os.path.realpath(f) for f in files if f.strip()}:
        return ""
    return f"not one of this task's files: {path[:80]}"


def decide_tool(tool: str, command: str, prefixes: list[str], background: bool = False,
                path: str = "", files: list[str] | None = None) -> str:
    """The hook runs for EVERY tool: an allowlist only adds to the tools a
    session inherits (MCP servers, Monitor), so the surface is closed here.
    A live command runs in the foreground: one left running in the
    background is killed half-done when the builder exits."""
    if tool not in ALLOWED_TOOLS:
        return f"the tool {tool} is not part of a live task"
    if tool in WRITERS:
        return decide_file(path, files or [])
    if tool != "Bash":
        return ""
    if background:
        return "a live task's command runs in the foreground, never in the background"
    return decide(command, prefixes)


def main() -> None:
    try:
        body = json.load(sys.stdin)
        tool_input = body.get("tool_input") or {}
        why = decide_tool(str(body.get("tool_name") or ""), str(tool_input.get("command") or ""),
                          os.environ.get("LIVE_ALLOWED_PREFIXES", "").split("\n"),
                          background=bool(tool_input.get("run_in_background")),
                          path=str(tool_input.get("file_path") or ""),
                          files=os.environ.get("LIVE_ALLOWED_FILES", "").split("\n"))
    except BaseException as error:   # noqa: BLE001 — a guard that cannot decide denies
        why = f"the live guard could not read the call: {error!r}"
    if why:
        print(why, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
