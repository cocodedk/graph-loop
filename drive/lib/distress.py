"""The builder's last word, as JSON with fixed flags.

The owner, 2026-08-28: "it must respond in json with deterministic flags". So every
builder ends with one line and nothing after it:

    {"result": "DONE", "blocked": false, "needs_person": false, "why": ""}
    {"result": "BLOCKED", "blocked": true, "needs_person": true,
     "why": "the fix needs a verb the agent does not have"}

`result` is one of DONE, BLOCKED, PARTIAL. The flags are what the loop reads;
the prose is for the person who gets paged. When the line is missing or
malformed, the answer is UNCLEAR and a person is told — never a guess. A DONE
that sets `needs_person` or `blocked` is read as BLOCKED: the card parks for
the person either flag asks for.
"""

from __future__ import annotations

import dataclasses
import json

STATES = ("DONE", "BLOCKED", "PARTIAL")
STUCK_WORDS = ("i cannot", "i can not", "unable to", "am stuck", "ambiguous",
               "unclear", "permission denied", "not allowed", "i stopped",
               "cannot proceed", "needs a decision", "out of scope")

TEMPLATE = ('{"result": "DONE|BLOCKED|PARTIAL", "blocked": true|false, '
            '"needs_person": true|false, "why": "one line, empty when DONE"}')


@dataclasses.dataclass
class Result:
    state: str                 # DONE | BLOCKED | PARTIAL | UNCLEAR
    why: str = ""
    blocked: bool = False
    raw: str = ""

    @property
    def needs_a_person(self) -> bool:
        return self.state != "DONE"


def closed_object(pairs: list[tuple[str, object]]) -> dict:
    """One JSON object, refusing a key given twice.

    `json.loads` keeps the last of two same-named keys, so an answer could
    carry `{"result": "BLOCKED", "result": "DONE"}` and the loop read whichever
    one it kept. `review.py` reads the reviewer's answer through this too.
    """
    if len(pairs) != len({key for key, _value in pairs}):
        raise ValueError("a JSON key was given twice")
    return dict(pairs)


def _from_json(line: str) -> Result | None:
    try:
        body = json.loads(line, object_pairs_hook=closed_object)
    except ValueError:
        return None
    if not isinstance(body, dict) or "result" not in body:
        return None
    state = str(body.get("result") or "").strip().upper()
    if state not in STATES:
        return Result("UNCLEAR", f"result was {state!r}, which is not one of "
                      + ", ".join(STATES), raw=line)
    why = str(body.get("why") or "").strip()
    stopped = [name for name in ("needs_person", "blocked") if bool(body.get(name))]
    if state == "DONE" and stopped:
        # It says finished and raises a flag that stops it in the same line.
        # The flag wins: the card parks for a person instead of passing as done.
        state = "BLOCKED"
        why = why or f"it said DONE and set {' and '.join(stopped)}"
    return Result(state, why, blocked=bool(body.get("blocked")), raw=line)


def read_result(text: str) -> Result:
    """The last JSON line the builder wrote, or UNCLEAR with the reason.

    Only that line is read. The scan used to walk on past a line it could not
    read, so a DONE with a broken result line under it was recorded as DONE —
    a line that opened an object and never finished it, the shape a blockage
    cut off part way leaves, was skipped the same way.
    """
    for line in reversed([one.strip() for one in (text or "").splitlines() if one.strip()]):
        if line.startswith("{"):
            return _from_json(line) or Result(
                "UNCLEAR", "the last result line could not be read", raw=line)
    low = (text or "").lower()
    for word in STUCK_WORDS:
        if word in low:
            return Result("UNCLEAR", f"no result line, and it said {word!r}", raw=text[-240:])
    return Result("UNCLEAR", "no result line", raw=(text or "")[-240:])


def tail(text: str, keep: int = 240) -> str:
    """The last thing it said, for a message a person reads on a phone."""
    return " ".join((text or "").split())[-keep:]
