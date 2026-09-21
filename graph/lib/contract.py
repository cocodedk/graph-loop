"""The contract a card carries: its words, its short name, and whether the card
in front of a write is still the one the round started from.

Split out of `prompts.py` at the 200-line cap; `prompts.py` imports the names
back, so every site that says `from prompts import contract_prompt` (or
`contract_digest`, `already_read`, `moved_under`) still reaches them there.
This module is the contract itself; `loop_contract.py` is the STEP that asks a
reviewer to read it.
"""

from __future__ import annotations

import hashlib
import json

from backlog_status import is_live
from contract_fixtures import question as fixture_question
from contract_uses import question as uses_question

# The rest of the contract: what the card waits for, the names it reads and
# writes, the phrase its red proof must print, and the card it was cut from.
# Shown only when the card carries one, always in this order, so one contract
# has one digest however the card was written.
REST = (("waits for", "needs"), ("uses", "uses"), ("creates", "creates"),
        ("gate_until_kept", "gate_until_kept"), ("gate_when_kept", "gate_when_kept"),
        ("red proof must contain", "expect_red"), ("sliced from", "sliced_from"))


def field(label: str, value: object) -> str:
    """One field of the contract, on its own line, as JSON.

    JSON so a boundary is a boundary. Pasted in raw, a note ending in a line
    that reads `waits for: ['T0']` gave the same text — and the same digest —
    as a card that really waits for T0, so a dependency added mid-round was
    invisible and the card was published over (Codex, 2026-09-08). A value
    cannot carry a newline through `json.dumps`, so every newline in this text
    starts a real field. `ensure_ascii=False` keeps non-ASCII characters
    readable — a reviewer has to recognise `café.py` — while quotes,
    backslashes and control characters are still escaped. A list of
    names is sorted, because its order is not part of the contract, so
    reordering one is not an edit the reviewer must read again.
    """
    if isinstance(value, list):
        value = sorted(str(name) for name in value)
    return f"{label}: {json.dumps(value, default=str, ensure_ascii=False)}\n"


def frozen_requirement(task: dict) -> dict:
    """The host freezes the granted requirement before any rewrite, so both
    reviewers can see if a rewrite dropped behaviour. No model writes it.
    """
    return {"goal": task.get("goal"), "done_when": task.get("done_when"),
            "sources": [str(one) for one in task.get("source") or []]}


def contract_text(task: dict) -> str:
    """The contract itself, in the words both reviewers are shown it in.

    One text, so the diff reviewer judges the change against the contract that
    was accepted — its note, its gate, its waits, its names, its red proof and
    its granted authority included, not a wider one it imagines from the goal
    alone. Everything here is digested, so editing any of it is an edit the
    reviewer has to read again.
    """
    return (
        field("id", task.get("id"))
        + field("goal", task.get("goal"))
        + field("files", task.get("files")).rstrip("\n")
        + (" (and NEW files beside them, same directories, for a split)\n"
           if task.get("may_add_files") else "\n")
        + field("gate", task.get("gate"))
        + field("done when", task.get("done_when"))
        + field("note", task.get("note", ""))
        + "".join(field(label, task[key]) for label, key in REST if task.get(key))
        + (field("the requirement this card was granted under, frozen before any "
                 "rewrite", task["requirement"]) if task.get("requirement") else "")
        + (field("helper verbs (the ONLY live commands its builder gets, verb plus the "
                 "arguments fixed here)", task.get("helper_verbs")) + "\n"
           if is_live(task) else "\n"))


def contract_prompt(task: dict) -> str:
    # What actually guards a self-written gate depends on the card: a live gate
    # is never run before the work (red-first is skipped), so its guard is the
    # helper whitelist, not a red proof — the prompt must not claim otherwise.
    honesty = ("its builder's only live commands are the helper verbs named below"
               if is_live(task) else
               "the gate is proved red in the worktree before the builder starts")
    writes_its_test = (
        "\nThis task writes the test its gate runs: that is the deliverable, not a "
        "loophole. The test does not exist yet, so nothing else could prove the "
        f"behaviour, and two things keep it honest — {honesty}, and you review the "
        "finished diff afterwards with this goal in hand. The gate runs exactly "
        "what its own text runs — no more; judge it by that text, never by a "
        "wider claim. "
        "Do not refuse it for being able to edit that file; judge whether the goal "
        "and the done-when say plainly what the test must assert.\n"
        if task.get("gate_files_are_the_work") else
        "\nRefuse it if the builder can edit the test its gate runs: the builder "
        "must not touch what judges it unless gate_files_are_the_work.\n")
    return (
        "Review this task contract before anyone edits a file. Can this gate pass without "
        "the work being done, and do the files cover what the gate can fail on? "
        "Name a concrete bypass or a blocking file. Refuse those defects, work broader "
        "than one idea, or authority the goal does not grant. Incidental implementation "
        "description in Goal/Done-when/Note need not be mechanically asserted by the gate. "
        "The behavioural requirement stays visible and must not be narrowed. "
        "Assume an honest builder whose diff is reviewed afterwards: a bypass only a "
        "deliberately deceptive builder would write (hard-coding the judge's expected values, "
        "a lookup table keyed on test data) is the diff review's finding, not grounds to "
        "refuse a contract.\n"
        + ("Refuse a rewrite that proves less than the requirement recorded below.\n"
           if task.get("requirement") else "")
        + writes_its_test + uses_question(task) + fixture_question(task) + "\n"
        + contract_text(task)
        + "Answer with one line of JSON and nothing after it:\n  "
        '{"review": "ACCEPT|REJECT", "accept": true|false, '
        '"findings": ["one line each, at most three"]}')


def contract_digest(task: dict) -> str:
    """What the contract reviewer actually read, as one short name.

    The prompt IS the contract: goal, gate, done_when, files and every flag the
    reviewer is shown. Digesting it needs no list of fields to keep in step, and
    any edit to any of them changes the answer.
    """
    return hashlib.sha256(contract_prompt(task).encode("utf-8")).hexdigest()[:16]


def already_read(task: dict, in_place: bool, reviewed_first: bool) -> bool:
    """Whether the contract in front of this round has been reviewed already.

    A rebuild round skips the review because round one accepted the contract —
    but only the contract it accepted. A card whose goal, gate, files, waits,
    names or red proof were edited after that acceptance (by a person, by a
    replan, by a slice) is a contract nobody has read, and building it would be exactly the thing the
    review exists to prevent.
    """
    if not (in_place or reviewed_first):
        return False
    if not task.get("requirement"):
        # The requirement is frozen AT a review, and a card approved before
        # there was one carries a digest that still matches: skipping the
        # review here left that card with nothing recorded to judge a later
        # rewrite against, for ever (Codex, 2026-09-08).
        return False
    seen = str(task.get("contract_seen") or "")
    return bool(seen) and seen == contract_digest(task)


# Everything that makes a card the one a call started from: why it moved, and
# how to read the field it moved in. `revision` digests the same readers, so a
# note written before a keep and a card read a turn later are compared by the
# one rule rather than by two lists that drift.
MOVED = (
    ("a person changed this card's hold while the call ran",
     lambda card: str(bool(card.get("blocked_by_human")))),
    # `needs` had its own entry until the contract text carried it; the digest
    # reads it now, sorted the same way, so a second reading would say nothing
    # the first does not.
    ("this card's contract was edited while the call ran", contract_digest),
    ("this card's status changed while the call ran",
     lambda card: str(card.get("status") or "")),
)


def moved_under(fresh: dict | None, started: dict) -> str:
    """Why the card is no longer the one this call started from — "" when it is.

    A person can hold a card, release it, drop it, edit its contract or change
    what it waits for WHILE a model call runs. Whatever that call decided was
    decided from the older card, and writing it afterwards clears the hold or
    buries the edit. Every site that writes a card after a long call asks this
    under the backlog lock, before it writes, and preserves its work instead of
    overwriting the newer decision.

    A status the LOOP itself writes mid-round is its own move, not a person's:
    the site that writes it says so on the card it carries (`loop_steps.build`
    and `live_call_open`), so this stays one rule with no exceptions in it.
    """
    if fresh is None:
        return f"{started.get('id')} is no longer in the backlog"
    for why, read in MOVED:
        if read(fresh) != read(started):
            return why
    return ""


def revision(task: dict) -> str:
    """All of what `moved_under` compares, as one short name a record can hold.

    A crash-recovery note says the branch holds a card's keep; only the card's
    revision AT THAT KEEP says whether the card has been decided again since.
    """
    return hashlib.sha256(
        "\n".join(read(task) for _, read in MOVED).encode("utf-8")).hexdigest()[:16]
