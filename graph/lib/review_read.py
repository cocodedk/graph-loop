"""What a reviewer's reply means, apart from how it was asked for.

Split out of `review.py` at the 200-line cap; `review.py` stays the front door
and re-exports `_read_review`, which is the name every caller and test knows.
"""

from __future__ import annotations

import json

import distress
import review_scope
from review_scope import (
    VERDICT,  # noqa: F401 — the shape's door stays beside its parser
)


def _read_review(text: str) -> tuple[str | None, str]:
    """A review's verdict and its findings, from every answer in the reply.

    Scoped diff answers are read whole first; the remaining parser below
    handles the legacy contract-review format.

    JSON is what the prompt asks for and what the log stores; the old
    `REVIEW: ACCEPT` line is still read so a reviewer that answers the old way
    is understood rather than discarded.

    The reply is untrusted input, read as the closed shape the prompt asked
    for (`prompts.py`): exactly `review`, `accept` and `findings`, nothing
    else — `review` the literal word the prompt declared, not any casing of
    it. `review` and `accept` naming different verdicts, `findings` holding
    anything but a short list of strings, at most three (the count
    `prompts.py` promises the model), or a key added or missing, is not a
    verdict to trust — it is malformed, the same as no verdict at all.

    The old line is read the same way: one distinct verdict in the whole
    answer, or none. It used to be read forwards, so `REVIEW: ACCEPT` followed
    by `REVIEW: REJECT` was recorded as an accept — the reviewer contradicting
    itself is not a verdict either.

    Both formats are read together, once, because they used to be read in
    turn: a JSON ACCEPT with `REVIEW: REJECT` under it returned the accept and
    the second answer was never seen. Every answer in the reply says the same
    one word or there is no verdict, and a JSON answer that is not the closed
    shape is a broken answer, never a line to step over on the way to an
    older one.

    The scoped shape is read by `review_scope.read`, which takes the whole reply
    and knows what prose around one answer means; the loop below is only ever
    the legacy shape. Both refuse a reply holding two answers, agreeing or not,
    because a reviewer that wrote two has not decided which contract it
    answered.
    """
    text, said = distress.answer(text)
    if said.state in ("BLOCKED", "PARTIAL"):
        return "BLOCKED", said.raw
    try:
        whole = review_scope.read(text)
    except ValueError:
        pass
    else:
        return whole["review"], text        # the raw text: `validate` re-reads it
    said: set[str | None] = set()
    findings = ""
    for line in [one.strip() for one in text.splitlines() if one.strip()]:
        if line.startswith("{"):
            answer = _json_verdict(line)
            if answer is None:
                continue                  # an object, but not an answer at all
            said.add(answer[0])
            findings = answer[1] or findings
        elif line.startswith("REVIEW:"):
            said |= {one for one in line.split(":", 1)[1].upper().split()[:1]
                     if one in ("ACCEPT", "REJECT")}
    if len(said) != 1 or None in said:
        return None, text
    return said.pop(), findings or text


def _json_verdict(line: str) -> tuple[str | None, str] | None:
    """One JSON answer's verdict and its findings.

    `None` for the whole answer when the line is no answer at all — an object
    the reviewer wrote inside its findings, which decodes and carries no
    `review` key. `(None, "")` when it IS an answer and not the closed shape
    asked for: a key given twice, or a line that opened an object and never
    finished it, which is a rejection cut off part way and never a line to
    skip on the way to an older accept.

    The line is decoded before its keys are read, so `"\\u0072eview"` is the
    key `review`: a filter on the raw text let an escaped key through unread.
    """
    try:
        body = json.loads(line, object_pairs_hook=distress.closed_object)
    except ValueError:
        return None, ""
    if not isinstance(body, dict) or "review" not in body:
        return None
    word, accept, found = body.get("review"), body.get("accept"), body.get("findings")
    if (word not in ("ACCEPT", "REJECT")
            or set(body) != {"review", "accept", "findings"}
            or not isinstance(accept, bool)
            or not isinstance(found, list)
            or not all(isinstance(one, str) for one in found)
            or accept != (word == "ACCEPT")
            or len(found) > 3):
        return None, ""
    return word, "; ".join(found)
