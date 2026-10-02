"""What a reviewer's reply means, apart from how it was asked for.

Split out of `review.py` at the 200-line cap; `review.py` stays the front door
and re-exports `_read_review`, which is the name every caller and test knows.
"""

from __future__ import annotations

import json

from provider_words import closed_object
from review_scope import (
    VERDICT,  # noqa: F401 — the shape's door stays beside its parser
)


def _read_review(text: str) -> tuple[str | None, list[str]]:
    """A review's verdict and its findings, as a list, from every answer in the reply.

    The reply is untrusted input, read as the closed shape the prompt asked for (`review_scope.VERDICT`):
    exactly `review`, `accept` and `findings`, nothing else. `review` and `accept` naming different
    verdicts, `findings` holding anything but at most ten strings, or a key added, missing or given twice,
    is malformed, the same as no verdict at all. Every answer in the reply must say the same one word, or
    there is no verdict: a reviewer contradicting itself has not decided.
    """
    said: set[str | None] = set()
    findings: list[str] = []
    for line in [one.strip() for one in text.splitlines() if one.strip()]:
        if line.startswith("{"):
            answer = _json_verdict(line)
            if answer is None:
                continue                  # an object, but not an answer at all
            said.add(answer[0])
            findings = answer[1] or findings
    if len(said) != 1 or None in said:
        return None, []
    return said.pop(), findings


def _json_verdict(line: str) -> tuple[str | None, list[str]] | None:
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
        body = json.loads(line, object_pairs_hook=closed_object)
    except ValueError:
        return None, []
    if not isinstance(body, dict) or "review" not in body:
        return None
    word, accept, found = body.get("review"), body.get("accept"), body.get("findings")
    if (word not in ("ACCEPT", "REJECT")
            or set(body) != {"review", "accept", "findings"}
            or not isinstance(accept, bool)
            or not isinstance(found, list)
            or not all(isinstance(one, str) for one in found)
            or accept != (word == "ACCEPT")
            or len(found) > 10):
        return None, []
    named = [one for one in found if one.strip()]
    if word == "REJECT" and not named:   # the answer rule: a refusal names what is wrong
        return None, []
    return word, named
