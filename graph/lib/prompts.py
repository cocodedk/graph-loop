"""What the loop says to its two models, word for word.

Three prompts: the contract review (before anyone edits), the build (with the
previous round's findings on top when there are any) and the diff review. The
contract's own text, its digest and the check that the card has not moved under
a call live in `contract.py`; they are imported back here so every existing
`from prompts import ...` keeps working.
"""

from __future__ import annotations

from backlog_status import is_live
from contract import (  # split out at the 200-line cap; the old front door stays open
    already_read,  # noqa: F401
    contract_digest,
    contract_prompt,  # noqa: F401
    contract_text,
    moved_under,  # noqa: F401
    revision,  # noqa: F401
)
from distress import TEMPLATE as DISTRESS_TEMPLATE
from gate_script import gate_script_path
from review_scope import INSTRUCTION, numbered
from tools import helper, helper_commands
from worktree_lock import LIVE_STACK

DIFF_LIMIT = 60_000   # a diff longer than this is refused, never cut silently


class DiffTooLarge(Exception):
    """Raised by diff_prompt when a diff is longer than DIFF_LIMIT: a silent
    cut let a reviewer ACCEPT a change it never saw the rest of. The caller
    ends the round the way any rejected diff ends it, findings and all."""

    def __init__(self, size: int, limit: int = DIFF_LIMIT) -> None:
        super().__init__(f"diff is {size} characters, over the {limit} limit")
        self.size = size
        self.limit = limit


def build_prompt(task: dict, in_place: bool = False) -> str:
    findings = task.get("rejections") or []
    live = is_live(task)
    # A task whose gate acts on the live stack IS stack work: forbidding the
    # containers it names stopped T2's builder cold. A code task keeps the ban.
    stack = (f"The live stack ({LIVE_STACK}) is reached through the helper "
             f"`{helper()} <verb>` — this task's commands, exactly: "
             f"{'; '.join(f'`{c}`' for c in helper_commands(task)) or 'none named'} (the "
             "file's header describes each verb). Your tools allow no other shell command: "
             "no docker, no curl, no python. The gate proves what happened from durable "
             "state, and anything outside the task's named verbs and targets fails it. "
             if live else "Touch no container. ")
    # paid edits that could not be carried onto the moved base are a diff the
    # builder reapplies, findings or none, in place or on a clean checkout;
    # the pointer stands until a builder has read it
    lost = ("Earlier rounds' edits could not be carried onto the moved base; they are saved "
            f"as diffs at {', '.join(task['lost_edits'])} — read them and reapply here what "
            "still holds. " if task.get("lost_edits") else "")
    where = ("The work is already in this worktree — do not start over. " if in_place
             else "This is a clean checkout. " if lost
             else "The previous round's worktree was lost; this is a clean checkout, "
                  "so do the work again with the findings in hand. ") + lost
    # "recorded reasons", not "a reviewer refused": a harness fault (a timeout,
    # a crash, a review that did not happen) queues a round too, and a prompt
    # that invents a rejection sends the builder hunting for a finding nobody wrote.
    rebuild = (("The previous round of this work needs another pass. " + where
                + "Recorded reasons are historical findings: recheck each against the CURRENT "
                "files and gates, ignore one that no longer applies, and keep unresolved "
                "diff-review findings:\n"
                + "".join(f"  - {line}\n" for line in findings) + "\n")
               if findings else (where + "\n" if lost else ""))
    return (
        rebuild
        + f"Do exactly this, editing ONLY these files: {task.get('files')}\n\n"
        f"{task.get('goal')}\n\n"
        f"It is done when: {task.get('done_when')}\n"
        + ("You may also CREATE new files beside the FILES listed above, in those same "
           "directories, when a split needs them — no new directory, and nothing beside a "
           "directory you were given.\n" if task.get("may_add_files") else "")
        + f"{('Note: ' + task['note']) if task.get('note') else ''}\n\n"
        f"The loop proves it with: {task.get('gate')}\n"
        "You do not need to run the gate yourself — the loop runs it after you finish; "
        "if a command is denied, finish the edit and end normally, do not stop as BLOCKED for that.\n"
        + (f"Run it with: bash {gate_script_path(task)}\n"
           "That file holds the gate above, byte for byte, and is the ONE command you are "
           "granted for it — the gate is a script, and a grant for each program in it does "
           "not authorise the script. Do not improvise a compile or a chained command: "
           "that is what gets denied, and what it leaves in the tree gets the card refused "
           "for writing outside its files.\n" if str(task.get("gate") or "").strip() else "")
        + "Before you write a rule, find the service or module here that already "
        "follows it and follow that one: a second copy of an existing rule is how "
        "three services read the same key three ways and two of them were right. "
        "If you find a duplicate that is NOT yours to fix, name it in your final "
        "line and leave it: it becomes its own card with its own proof, and a "
        "refactor here would take you outside your files. "
        "Follow this repository's own written rules, CLAUDE.md first if it has one, "
        "inside your own files and under this gate. Never a tidy-up beside the work. "
        "Plain human language in every word you write. The simplest thing that "
        "works. Do not commit. " + stack + "\n\n"
        "End your answer with one line of JSON and nothing after it:\n  "
        + DISTRESS_TEMPLATE + "\n"
        "`result` is DONE when the edit is finished, BLOCKED when something stopped "
        "you, PARTIAL when some of it is done and the rest needs a decision. "
        "Say BLOCKED rather than guessing: nobody may be watching, and a "
        "blocked task is read by a person while a wrong guess is not.")


def diff_prompt(task: dict, diff: str) -> str:
    if len(diff) > DIFF_LIMIT:
        raise DiffTooLarge(len(diff))
    findings = task.get("rejections") or []
    return (
        "Review this finished change. You did not write it.\n\n"
        "The contract (goal, gate, done_when, files) is accepted and is not under review. "
        "Refuse only for what the change does or fails to do under that contract. A weakness "
        "of the gate or the criteria is an observation, not a refusal.\n\n"
        f"The contract it was built under, as accepted (contract {contract_digest(task)}):\n"
        + contract_text(task)
        + (("Earlier rounds of this work were sent back for these recorded reasons:\n"
            + "".join(f"  - {line}\n" for line in findings) + "\n") if findings else "")
        + "The numbered diff:\n"
        + numbered(diff)
        + "\n\nJudge it against that contract: its note is a boundary, and what the note "
        "forbids is not a finding.\n" + INSTRUCTION)
