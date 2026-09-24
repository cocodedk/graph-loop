"""What a builder may run, decided by the task — the one boundary a builder
cannot argue with.

A code task gets the shell its gates and tests need, minus one thing every
builder is denied: `git push`. A checkout is its own private clone, but a
push addressed by the repo's filesystem path lands on the REPO's own
receive-pack — the checkout's `core.hooksPath` never sees it, and
`receive.denyCurrentBranch` guards only the branch actually checked out
there, not a new one a push can name
(`test_worktree_private_refs.py::test_a_push_by_the_repos_own_path_is_stopped_by_the_tool_fence_not_the_hook`
shows the raw push this deny stops). The deny is a pattern on the builder's
tool permissions, not a sandbox: a shell that addresses the repository by
path is outside what a pattern can see, and a read-only mount of the
repository for the builder is its own cartridge. A live task
(`gate_has_side_effects`) gets three more fences, innermost first:
1. the live guard (`live_guard.py`, a PreToolUse hook the provider installs
   with `--settings`): a whitelist of this task's exact commands — the helper
   by the main checkout's absolute path (never a worktree copy) followed by
   each entry of the contract's `helper_verbs` (a verb and the arguments the
   contract fixes, e.g. "free prd-app-04"; `newpkg`/`next` write the checkout
   and can never be named), plus cat/ls/head/tail — with no shell control
   character, so nothing chains, redirects or wraps;
2. the allow rules (`--allowedTools`): the same commands, so they run without
   a prompt, plus Read/Grep/Glob and Edit on the task's own files (an Edit
   rule governs Write too);
3. deny rules for the raw stack, a last fence against an inherited allow.
Arguments the contract cannot know in advance (a run id born in the task)
are left open in the entry and bound by the gate's proof from durable state.
"""

from __future__ import annotations

import os
import pathlib
import re

import where
from backlog_status import is_live
from code_grant import (  # noqa: F401 — the door
    BASE_SHELL,
    NEVER_WILDCARD,
    code_shell,
)
from gate_script import gate_script_path, write_gate_script  # noqa: F401 — the door


def helper() -> str:
    """The repository's own command tool, if it has one, as an absolute path.

    A live task drives the thing being built through one helper command rather
    than a shell. Which command that is belongs to the repository being worked
    on, not to this loop, so `GRAPH_HELPER` names it; with nothing named, a
    task gets no helper grant at all.
    """
    return os.environ.get("GRAPH_HELPER", "")
LIVE_VERBS = ("run", "declare", "journal", "why", "rebuild", "free", "reject", "story",
              "target-state", "reset-target")
OPEN_VERBS = ("journal", "why", "story")   # their argument is a run id born in the task; every other verb's is fixed
# A bound verb carries ALL its arguments: the helper defaults nothing for a builder
# ("run FND-X" alone would let sc pick the target). reject takes the finding and the target.
BOUND_ARITY = {"run": 2, "declare": 2, "reject": 2, "free": 1, "target-state": 1, "reset-target": 1, "rebuild": 1}
READ = "Read,Grep,Glob"
LIVE_SHELL = "Bash(cat *),Bash(ls *),Bash(head *),Bash(tail *)"
READ_ONLY_DENIES = ("Bash,Edit,Write,NotebookEdit,Monitor,Workflow,Task,"
                    "WebFetch,WebSearch,KillShell,BashOutput")
"""What a reviewer may not have. `--allowedTools` is additive, so naming only
Read/Grep/Glob leaves everything the session already had — including Bash and
Edit. A reviewer that can write can alter what it grades."""

READ_ONLY_FLAGS = ("--tools", READ, "--strict-mcp-config")
"""What bounds a call that may only read: `--tools` replaces the built-in set
instead of adding to it, and `--strict-mcp-config` leaves an inherited MCP
server out. Denying by name cannot reach a server nobody here has heard of.
Every read-only call reads this one list — the reviewer and the planner."""

STACK_DENIES = ("Monitor,Workflow,"   # tools that run commands of their own, past the Bash hook
                "Bash(docker *),Bash(docker-compose *),Bash(curl *),Bash(wget *),Bash(python3 *),"
                "Bash(python *),Bash(bash *),Bash(sh *),Bash(psql *),Bash(nc *),Bash(socat *)")
PUSH_DENY = "Bash(git push *)"   # every builder, CODE and live alike — see the module docstring
ENTRY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:-]*$")   # one line, plain characters: no newline can add a prefix


LIVE_PLAIN = ("cat", "ls", "head", "tail")


def helper_commands(task: dict) -> list[str]:
    """This task's helper commands: each `helper_verbs` entry whose verb is a
    live verb and whose text is one plain line. A bare verb is open (its
    arguments are born in the task: "journal *"); a verb with arguments is
    the whole command ("free prd-app-04")."""
    entries = [str(entry).strip() for entry in (task.get("helper_verbs") or [])]
    def complete(entry: str) -> bool:
        verb, args = entry.split()[0], entry.split()[1:]
        if verb in OPEN_VERBS:
            return True                        # open: bare, or with the argument born in the task
        return verb in BOUND_ARITY and (len(args) == BOUND_ARITY[verb] or (verb == "rebuild" and bool(args)))
    home = helper()
    if not home:
        return []
    good = [entry for entry in entries if ENTRY.match(entry) and entry.split()[0] in LIVE_VERBS and complete(entry)]
    return [f"{home} {entry}" + (" *" if " " not in entry else "") for entry in good]


def builder_tools(task: dict, root: str = "") -> str:
    """The --allowedTools string; file scope is checked after the build."""
    if not is_live(task):
        # The scope check bounds the files, whichever writing tool is used.
        return f"{READ},Edit,Write,{code_shell(task)}"
    own = ",".join(f"Edit({path})" for path in (task.get("files") or []))
    verbs = ",".join(f"Bash({command})" for command in helper_commands(task))
    return ",".join(part for part in (READ, own, verbs, LIVE_SHELL) if part)


def builder_guard(task: dict) -> str:
    """The live guard's entries, one per line; empty for a code task."""
    if not is_live(task):
        return ""
    return "\n".join(helper_commands(task) + [f"{plain} *" for plain in LIVE_PLAIN])


def guard_files(task: dict, cwd: str) -> str:
    """The files a live task's writers may touch, absolute in its worktree,
    one per line; empty for a code task."""
    if not is_live(task):
        return ""
    return "\n".join(str(pathlib.Path(cwd) / path) for path in (task.get("files") or []))


def guard_settings() -> dict:
    """The settings the provider installs for a live task: the hook, by the
    main checkout's path."""
    hook = f"python3 {where.loop()}/graph/lib/live_guard.py"
    return {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": hook}]}]}}


def builder_denies(task: dict) -> str:
    """The --disallowedTools string: the push deny always, plus the raw
    stack for a live task — the base shell's `Bash(git *)` would otherwise allow
    the push a deny rule is needed to beat."""
    stack = STACK_DENIES if is_live(task) else ""
    return ",".join(part for part in (stack, PUSH_DENY) if part)
