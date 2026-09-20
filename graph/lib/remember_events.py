"""One campaign event as one dated section of a node's memory.

It points and never copies. A section carries the event's own time, the numbers
the log recorded, and the NAME of the numbered artifact file that holds the
words — never the reviewer's text, never what the gate printed, never a path
off the machine that ran the campaign. The log stays the one home of the raw
record; the note is the short, durable part that travels with the card in git.

Five things a node remembers, as the log spells them: `planned` (the plan phase
grew the backlog by this card), `attempt` (one answered call and how it ended),
`refused` (which names the step it happened at) and `rejected` (which names
nothing), a `step` of the `gate` (its exit code and its seconds) and `accepted`
(the keep, with its commit).

A section says what the log says and not one word more. `rejected` is the case
that taught it: the loop writes that same event when a diff review finds
something, when a harness retry runs out and when a gate never passes
(`loop_judge_retry.py`, `worktree_refs.py`), and the event carries nothing to
tell those apart — so the section says the card was rejected, points at the
log, and names no reviewer and no file.

Every other kind is counted and left out, because a note that reprints the log
is the log twice. `failed` is left out on purpose: the loop writes one beside
every red gate, its `why` is the gate's own output, and the `step` above
already carries the exit code that says the same thing.
"""

from __future__ import annotations

import pathlib

READ = ("attempt", "refused", "rejected", "accepted", "step")


def dated(rows: list) -> tuple[dict, dict]:
    """Every node's sections, in the order the log wrote them, and the counts.

    Three ways an event ends up in none of them, each counted apart: a row that
    is not an event this can read at all, a kind it has no section for, and a
    kind it does know about that names no node it can use.
    """
    memory: dict[str, list] = {}
    counts = {"no_section": 0, "unreadable": 0}
    found = _artifacts(rows)
    for index, row in enumerate(rows):
        if not _readable(row):
            counts["unreadable"] += 1
            continue
        made = _section(row, found, index)
        if made is None:
            counts["no_section"] += 1
            continue
        nodes, summary, body = made
        if not nodes:
            counts["unreadable"] += 1
            continue
        for node in nodes:
            memory.setdefault(node, []).append(
                (f"{row['at'][:10]} — {summary}",
                 f"{row['at']}. {body[:1].upper()}{body[1:]}"))
    return memory, counts


def _readable(row) -> bool:
    """Whether this is an event at all: a mapping, with a time and a kind."""
    return (isinstance(row, dict) and isinstance(row.get("kind"), str)
            and isinstance(row.get("at"), str) and len(row["at"]) >= 10)


def _section(row: dict, found: dict, index: int):
    """This event as (the nodes it is about, its heading, its body), or None
    when a memory has no section for its kind."""
    if row["kind"] == "planned":
        added = row.get("added")
        names = [name for name in added if isinstance(name, str)] \
            if isinstance(added, list) else []
        return names, "planned", "the plan phase added this card."
    if row["kind"] not in READ or (row["kind"] == "step" and row.get("step") != "gate"):
        return None
    task = row.get("task")
    if not isinstance(task, str) or not task:
        return [], "", ""
    summary, body = _BUILD[row["kind"]](row)
    name, after = _wanted(row)
    where = _written_for(found, index, task, name, after) if name else ""
    if where:
        said = "What it printed" if name == "gate-output" else "Its own words"
        body += f" {said}: calls/{task}/{where}"
    return [task], summary, body


def _attempt(row: dict) -> tuple[str, str]:
    told = [f"on the {row.get('account') or 'unnamed'} account"]
    if row.get("purpose"):
        told.append(f"for the {row['purpose']}")
    told.append("it counted as an attempt" if row.get("counted") else "it did not count")
    if _number(row.get("cost")) is not None:
        told.append(f"${row['cost']:.4f}")
    if _number(row.get("tokens")) is not None:
        told.append(f"{row['tokens']} tokens")
    if row.get("failed_gate"):
        told.append("the gate was red")
    return f"an attempt, ended {row.get('outcome') or 'unrecorded'}", ", ".join(told) + "."


def _refused(row: dict) -> tuple[str, str]:
    return f"refused at {row.get('step') or 'a review'}", "a review sent it back."


def _rejected(row: dict) -> tuple[str, str]:
    return "rejected", ("the card was rejected. This event does not say what decided "
                        "it, so neither does this: read the campaign log at this time.")


def _gate(row: dict) -> tuple[str, str]:
    code, seconds = _number(row.get("code")), _number(row.get("seconds"))
    ran = f"exit {code}" if code is not None else "no exit code recorded"
    took = f" after {seconds} seconds" if seconds is not None else ""
    return f"the gate ran, {ran}", f"{ran}{took}."


def _accepted(row: dict) -> tuple[str, str]:
    commit = row.get("commit")
    if isinstance(commit, str) and commit:
        return "kept", f"kept on the campaign branch as commit {commit}."
    return "accepted", "accepted, with nothing to commit."


_BUILD = {"attempt": _attempt, "refused": _refused, "rejected": _rejected,
          "step": _gate, "accepted": _accepted}

# Which numbered artifact a section points at. By its recorded NAME and
# nothing else: the nearest artifact of any name could be a prompt, and a
# section that names the prompt instead of the answer sends the reader to the
# wrong file for ever.
_POINTS_AT = {"contract": "contract-answer", "red_first": "red-first"}


def _wanted(row: dict) -> tuple[str, bool]:
    """The artifact this section points at, and whether the loop writes it
    AFTER its event: a gate's output lands after the step that ran the gate
    (`loop_judge.judge`), a reviewer's answer before the refusal it caused."""
    if row["kind"] == "refused":
        return _POINTS_AT.get(row.get("step"), ""), False
    return ("gate-output", True) if row["kind"] == "step" else ("", False)


def _artifacts(rows: list) -> dict:
    """Where each (task, artifact name) was written, in one pass over the log."""
    found: dict = {}
    for index, row in enumerate(rows):
        if (isinstance(row, dict) and row.get("kind") == "artifact"
                and isinstance(row.get("path"), str)
                and isinstance(row.get("task"), str)
                and isinstance(row.get("name"), str)):
            # Every one of those three checked before any of them is a key: a
            # row whose `task` is a list is unhashable, and it took the whole
            # export down with a TypeError before the counting even began.
            found.setdefault((row["task"], row["name"]), []).append((index, row["path"]))
    return found


def _written_for(found: dict, index: int, task: str, name: str, after: bool) -> str:
    """The file name of the artifact THIS run wrote: of this task, of this
    name, and the first one on the side the loop writes it — after the event
    for a gate's output, before it for a reviewer's answer.

    Never the closest one. A campaign writes one stream and three cards write
    into it at once, so distance in that stream is a fact about the other
    lanes: with two of them logging in between, a green gate was made to name
    the red run's output (an independent review). Distance is gone; only this
    task's own artifacts are looked at, and only on the one side.

    A run whose artifact never landed — a campaign that died between the two —
    names no file. No pointer is better than a pointer at another run's words.

    The NAME only, never the recorded path: that path is absolute, it names the
    machine the campaign ran on, and these notes are committed to the campaign
    branch where a person reads them in Obsidian.
    """
    written = found.get((task, name)) or []
    side = [path for where, path in written if (where > index) == after
            and where != index]
    if not side:
        return ""
    return pathlib.PurePosixPath(side[0] if after else side[-1]).name


def _number(value):
    """The value when it is a number the note can print, None otherwise. A
    bool is not one: `True` would read back as `1` and say something false."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
