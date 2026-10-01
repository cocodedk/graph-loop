"""The words that classify a refusal, split out of `providers` at the
200-line cap. `providers` re-exports all of this — it stays the front door
other modules import from.
"""

from __future__ import annotations

import re

from gate_programs import programs

LIMIT_MARKS = ("hit your weekly limit", "hit your session limit",
               "usage limit", "resets ", "quota", "http 429", "status 429",
               "rate limit", "rate_limit", "too many requests")
CAPACITY_MARKS = ("at capacity", "try a different model", "overloaded",
                  "is not supported when using", "model metadata for", "model_not_found",
                  "network failure", "network error", "connection reset", "econnreset",
                  "gateway timeout", "service unavailable", "internal server error", "bad gateway")
HTTP_5XX = re.compile(r"\b(?:http(?:/\d(?:\.\d)?)?|error|status(?: code)?)\s*[:=]?\s*5[0-9]{2}\b")
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

# The machine, like an unavailable provider, cannot reject the work.
ENVIRONMENT_MARKS = (
    (("sdk location not found", "android_home"),
     "set ANDROID_HOME to the Android SDK, or provision local.properties with sdk.dir"),
    (("java_home", "unable to locate a java runtime", "could not find tools.jar"),
     "install a JDK and set JAVA_HOME to it"),
    (("command not found",), "install the missing command and set PATH for the gate"),
)
MISSING_RUNNER = re.compile(
    r"(?:^|:\s+)(?P<runner>[^\s:'\"]+): No such file or directory", re.IGNORECASE | re.MULTILINE)


def environment_hint(text: str, gate: str) -> str:
    """A failed gate's missing toolchain, never a missing input or test fixture."""
    low = text.lower()
    for marks, remedy in ENVIRONMENT_MARKS:
        if any(mark in low for mark in marks):
            return remedy
    runners = programs(gate)
    for found in MISSING_RUNNER.finditer(text):
        if found["runner"].rsplit("/", 1)[-1] in runners:
            return "restore the gate's runner and set PATH to its toolchain"
    return ""


def _classify_text(text: str) -> str | None:
    low = text.lower()
    if (any(mark in low for mark in CAPACITY_MARKS)
            or HTTP_5XX.search(low)
            or all(mark in low for mark in CODEX_BACKEND_OUTAGE_MARKS)):
        return "capacity"      # provider unavailable, never a finding against the card
    if any(mark in low for mark in LIMIT_MARKS):
        return "limit"
    if any(mark in low for mark in AUTH_MARKS):
        return "auth"
    return None


def _classify_failure(body: dict, returncode: int, text: str) -> str | None:
    """Read the error's own status even when its result carries no error words.

    Successful answers may discuss HTTP failures; only failed calls have their
    words classified. Capacity uses the existing uncharged retry and cooldown.
    """
    status = body.get("api_error_status")
    if isinstance(status, int) and 500 <= status < 600:
        return "capacity"
    if body.get("subtype") == "error_max_budget_usd":
        return "budget"
    if returncode or body.get("is_error"):
        return _classify_text(text) or "crash"
    return None


def budget_words(body: dict, budget: float | None) -> str:
    """What a spend-cap stop says. The CLI's own words only say it stopped: this says what to do."""
    spent = body.get("total_cost_usd")
    cap = f"${budget:g}" if isinstance(budget, (int, float)) else "its limit"
    cost = f"${spent:.2f}" if isinstance(spent, (int, float)) and not isinstance(spent, bool) else "an unknown amount"
    return (f"the builder reached its spend cap of {cap} (it had spent {cost}); its work so far "
            "is kept. Reslice or simplify the card, or raise CARD_BUDGET in graph/lean_budget.py if the card "
            "is right, then run it again. The cap is checked per turn, so one long turn can pass it.")


def closed_object(pairs: list[tuple[str, object]]) -> dict:
    """A JSON object with one key twice is not one shape; it is two.

    Every model answer this loop parses goes through here: what a repeated key
    means is the reader's guess, and a guess is not a closed shape.
    """
    if len(pairs) != len({key for key, _value in pairs}):
        raise ValueError("duplicate JSON key")
    return dict(pairs)


def _spent(body: dict) -> dict:
    """What the call spent, read from the answer's own numbers.

    A refusal carries them too — an expired session answers with
    total_cost_usd 0 and a usage block of zeros — and the error path used to
    drop them, so every refusal looked like it had spent nothing whether it had
    or not. A field that is absent stays None: unknown is not zero.
    """
    usage = body.get("usage")
    tokens = None
    if isinstance(usage, dict):
        # BOTH counts, or none. A block that reports zero input and omits output
        # says nothing about what it spent, and summing what is there reads that
        # silence as zero — which is the proof a live retry rests on.
        counts = [value for value in (usage.get("input_tokens"), usage.get("output_tokens"))
                  if isinstance(value, int) and not isinstance(value, bool)]
        tokens = sum(counts) if len(counts) == 2 else None
    denials = body.get("permission_denials")
    cost = body.get("total_cost_usd")
    # A JSON boolean is an int in Python: `false` would read as zero spend, and
    # zero spend is the proof a live action may be repeated.
    money = cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
    turns = body.get("num_turns")
    return {"cost": money, "tokens": tokens, "turns": turns if isinstance(turns, int) and not isinstance(turns, bool) else None,
            # A missing list is unknown, not "no denials": -1 says so, and
            # `unstarted` refuses anything that is not exactly zero.
            "denials": len(denials) if isinstance(denials, list) else -1}
