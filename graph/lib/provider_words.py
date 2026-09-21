"""The words that classify a refusal, split out of `providers` at the
200-line cap. `providers` re-exports all of this — it stays the front door
other modules import from.
"""

from __future__ import annotations

LIMIT_MARKS = ("hit your weekly limit", "hit your session limit",
               "usage limit", "resets ", "quota", "http 429", "status 429",
               "rate limit", "rate_limit", "too many requests")
CAPACITY_MARKS = ("at capacity", "try a different model", "model_overloaded",
                  "overloaded_error", "is not supported when using",
                  "model metadata for", "model_not_found", "network failure", "network error")
# codex's responses endpoint answered 404, not this repo's fault — 2026-09-03T15:02:59Z-15:03:13Z (one
# 14-second call, this loop's own review_unavailable record): read as "malformed"
# for want of this, and charged like a real finding. Both parts are required, and
# both name the TERMINAL failure only: the URL alone also names a 400 or a 401
# (their own kind, as today), and a non-terminal "failed to refresh available
# models" warning on /models is not this call giving up — codex retries past it.
CODEX_BACKEND_OUTAGE_MARKS = ("error: unexpected status 404 not found", "backend-api/codex/responses")
AUTH_MARKS = ("invalid api key", "please run /login", "not logged in",
              "not authenticated", "authentication failed",
              # the exact words a session that has expired answers with; without
              # it the loop filed an expired account as a crash for a whole night
              "failed to authenticate")


def _classify_text(text: str) -> str | None:
    low = text.lower()
    if (any(mark in low for mark in CAPACITY_MARKS)
            or all(mark in low for mark in CODEX_BACKEND_OUTAGE_MARKS)):
        return "capacity"      # the model refused before reading anything; another may answer
    if any(mark in low for mark in LIMIT_MARKS):
        return "limit"
    if any(mark in low for mark in AUTH_MARKS):
        return "auth"
    return None


def closed_object(pairs: list[tuple[str, object]]) -> dict:
    """A JSON object with one key twice is not one shape; it is two.

    Every model answer this loop parses goes through here: what a repeated key
    means is the reader's guess, and a guess is not a closed shape.
    """
    if len(pairs) != len({key for key, _value in pairs}):
        raise ValueError("duplicate JSON key")
    return dict(pairs)
