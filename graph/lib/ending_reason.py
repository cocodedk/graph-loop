"""A review's stated reason, before the context it quotes."""

from __future__ import annotations

import re

import review_scope
from review_read import _read_review


def review_reason(*fields: str | None) -> str:
    """Prefer the shortest verdict field; keep its first unquoted paragraph.

    Old refused events cut the answer at 400 characters. When that prefix is
    all the event holds, recover the complete paragraph from the other field.
    Raw answer artifacts are a fallback for callers without recorded findings.
    """
    reasons = []
    for field in fields:
        text = str(field or "").strip()
        if not text:
            continue
        try:
            text = review_scope.summary(review_scope.read(text))
        except ValueError:
            _, text = _read_review(text)
        text = re.sub(r"^REVIEW:\s*(?:REJECT|ACCEPT)\s*", "", text).strip()
        paragraph = re.split(r"\n\s*\n|\n(?=\s*(?:```|~~~|>))", text, maxsplit=1)[0]
        if paragraph:
            reasons.append((len(str(field).strip()), paragraph))
    complete = [(size, reason) for size, reason in reasons if not (
        len(reason) == 400 and any(other.startswith(reason) and other != reason
                                  for _, other in reasons))]
    return min(complete or reasons, key=lambda pair: pair[0], default=(0, ""))[1]
