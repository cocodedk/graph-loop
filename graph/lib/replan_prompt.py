"""The words a refused contract is handed back to the planner with.

Split from `replan.py` at the 200-line cap: that module decides what a rewrite
may do and writes it back, this one only asks. `replan.prompt_for` is still the
name every caller and test uses.
"""

from __future__ import annotations

import pathlib

import distress
from backlog_status import is_live
from contract import frozen_requirement
from worktree_scope import changed_outside


def _attempt_context(task: dict) -> str:
    tree = str(task.get("rebuild_from") or task.get("worktree") or "")
    if not tree:
        return ""
    changed = "unknown (attempt worktree unavailable)"
    if (pathlib.Path(tree) / ".git").exists():
        try:
            changed = repr(changed_outside(tree, []))
        except (OSError, RuntimeError):
            pass  # missing evidence never means that no files changed
    return (f"Previous attempt's uncommitted files: {changed}. These edits are not landed "
            "on the campaign branch and cannot prove this card is already complete; "
            "judge completion against the campaign branch tip.\n\n")


def prompt_for(task: dict) -> str:
    return (
        "Read and follow this repository's own written rules, CLAUDE.md first "
        "and the files it links, before writing a gate.\n\n"
        "A reviewer refused this task's contract. Rewrite the contract so the "
        "objection cannot be made again. Keep the same intent and the same files "
        "— you may drop a file, never add one — and keep it one idea. You may "
        "strengthen the gate or remove an unprovable sentence, but NEVER add a new claim "
        "to the goal or done-when and must not narrow the recorded requirement.\n\n"
        f"goal: {task.get('goal')}\n"
        f"files: {task.get('files')}\n"
        f"gate: {task.get('gate')}\n"
        f"done when: {task.get('done_when')}\n\n"
        f"Recorded requirement: {task.get('requirement') or frozen_requirement(task)}\n\n"
        f"What the reviewer said:\n{task.get('refused_why')}\n\n"
        + _attempt_context(task)
        + ("Earlier reasons this task was refused, oldest first — a rewrite that repeats one is refused again:\n"
           + "\n".join(f"- {why}" for why in task.get("replan_history") or []) + "\n\n"
           if task.get("replan_history") else "")
        + ("The gate performs the work on the live stack, so it is fixed and not yours "
           f"to change; it stays:\n{task.get('gate')}\n\n"
           if is_live(task) else
           "You may rewrite the gate, and if the reviewer's objection is about the gate you "
           "MUST. A gate is a command whose exit code is the verdict; it must FAIL on today's "
           "tree for the reason this task exists, and it must not be passable without the work. "
           "Before you answer, ask how someone could satisfy it while doing nothing, and close "
           "that way. Every path in it is relative to the worktree; each stage is its own "
           "`(cd ... && ...)`; its first line, alone, is exactly `set -e -o pipefail`. Never make it run a whole suite "
           "to prove a small change: a suite can go red for reasons this task's files cannot "
           "fix, and that refuses the task for the environment's faults. Never pin EXPECTED to a "
           "literal, to len(...), or to a value read from HEAD: the runner's EXPECTED counts "
           "test cases and moves as tests land, so assert it only against what the runner "
           "collects (`countTestCases()`/`run_all.EXPECTED`).\n\n")
        + "When the refusal names a concrete bypass that a frozen judge test misses, add an "
        "executed probe to THIS card's gate: the gate writes a small test file beside the project's "
        "tests, runs it with the project's test command, and removes it with a trap on exit. "
        "Assert exactly the named case so the bypass fails the gate; keep this card's files "
        "unchanged, with the probe only in the gate text. Never substitute greps or regexes "
        "on the source for a behavioural gap, and never ask for the judge to change.\n\n"
        + "A gate must never hide or delete the output a builder needs: no quiet flags "
        "that drop compiler errors, no deleting the log it greps. A stub's acceptance checks "
        "compilation/interface availability, never continued non-implementation.\n\n"
        "Answer with YAML using only these keys, followed by the distress line: goal, files, done_when"
        + ("." if is_live(task) else ", gate.")
        + " Keep the goal to one idea, name every file the gate can fail on, "
        "and say plainly what the gate will prove and what it will not.\n"
        + distress.INSTRUCTION + distress.TEMPLATE)
