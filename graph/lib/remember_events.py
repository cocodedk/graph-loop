"""One campaign event as one dated section of a node's memory.

It points and never copies. A section carries the event's own time, the numbers
the log recorded, and the NAME of the numbered artifact file that holds the
words — never the reviewer's text, never what the gate printed, never a path
off the machine that ran the campaign. The log stays the one home of the raw
record; the note is the short, durable part that travels with the card in git.

Five things a node remembers, as the log spells them: `planned` (the plan phase
grew the backlog by this card), `attempt` (one answered call and how it ended),
`refused` and `rejected` (a review sent the work back), a `step` of the `gate`
(its exit code and its seconds) and `accepted` (the keep, with its commit).

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
    where = _nearest(found, index, task, name, after) if name else ""
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
    return "the diff review sent it back", "the change was not accepted as it stood."


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
    if row["kind"] == "rejected":
        return "diff-review-answer", False
    return ("gate-output", True) if row["kind"] == "step" else ("", False)


def _artifacts(rows: list) -> dict:
    """Where each (task, artifact name) was written, in one pass over the log."""
    found: dict = {}
    for index, row in enumerate(rows):
        if (isinstance(row, dict) and row.get("kind") == "artifact"
                and isinstance(row.get("path"), str)):
            found.setdefault((row.get("task"), row.get("name")), []).append(
                (index, row["path"]))
    return found


def _nearest(found: dict, index: int, task: str, name: str, after: bool) -> str:
    """The file name of the artifact of this name written closest to this
    event, on the side the loop writes it. Both sides are searched, because a
    campaign that died between the two leaves only the other one; `after` is
    only which way a tie goes, and two gate runs in a row make that tie.

    The NAME only, never the recorded path: that path is absolute, it names the
    machine the campaign ran on, and these notes are committed to the campaign
    branch where a person reads them in Obsidian.
    """
    written = found.get((task, name)) or []
    if not written:
        return ""
    return pathlib.PurePosixPath(
        min(written, key=lambda pair: (abs(pair[0] - index),
                                       0 if (pair[0] > index) == after else 1))[1]).name


def _number(value):
    """The value when it is a number the note can print, None otherwise. A
    bool is not one: `True` would read back as `1` and say something false."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
