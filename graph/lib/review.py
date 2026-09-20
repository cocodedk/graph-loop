"""One review call: who is asked, and what their answer is worth.

Split out of `providers` at the 200-line cap; `providers` stays the front door.
What a reply MEANS split out of here at the same cap and lives in
`review_read`, which this module re-exports, so `review._read_review` still
names the parser wherever it was already called.
The reviewer is codex (gpt-6-astra first, gpt-5.6-sol behind it) at the rung lib/effort.py chose — never
`max`, which cost twelve minutes a review and found what high finds.
"""

from __future__ import annotations

import os

import resources
import tools
from provider_codex import codex_text
from providers import REVIEW_EFFORT, Outcome, _classify_text
from review_read import (  # noqa: F401 — this module is the front door
    VERDICT,
    _read_review,
)


def codex(binary: str, prompt: str, *, cwd: str = "", effort: str = "",
          timeout: int = 1800, attempt=None) -> Outcome:
    """A review, from the first reviewer that answers.

    `effort` is the rung lib/effort.py chose for the task; `max` is on no
    ladder — it cost twelve minutes a review (the owner, 2026-08-30).

    Every reviewer on the belt is tried in turn until one answers.
    A model at capacity refuses before reading anything, so the next one may
    answer the same question; one model name compiled in here is why three
    reviews came back empty on 2026-08-31 and their changes went in unreviewed.

    `cwd` is the worktree this review judges — never the driver's own
    checkout, or a reviewer that reads beyond the pasted diff reads the
    wrong tree.
    """
    out = Outcome("harness", text="the review belt is empty: no reviewer is configured")
    spent = resources.Exhausted()
    for resource in resources.belt("review"):
        if spent.skip(resource):
            continue
        out = (_one_review(binary, prompt, resource.model, cwd, effort, timeout)
               if resource.agent == "codex"
               else _claude_review(prompt, resource, effort, timeout, cwd=cwd))
        if attempt:
            # every belt member that was ASKED lands in the record, refusals
            # included, under its real account — one aggregate row hid them
            attempt(out.kind, resource.account, out.cost, out.tokens,
                    out.text or out.raw)
        if not resources.refused_before_reading(out.kind):
            return out          # an answer, or a fault another resource cannot fix
        spent.note(resource, out.kind)
    return out


def _claude_review(prompt: str, resource, effort: str, timeout: int, *, cwd: str = "") -> Outcome:
    """A review from claude, when codex cannot give one.

    It reads the repository and answers in the same shape. The allowlist alone
    would not bound it — `--allowedTools` adds to what the session already has —
    so it is bounded by `tools.READ_ONLY_FLAGS`, which replaces the built-in
    set and leaves an inherited MCP server out, and everything that writes or
    runs is DENIED by name on top: a reviewer that can write can alter what it
    grades. The verdict is read by the same parser, so a reviewer that answers
    the old `REVIEW: ACCEPT` way is understood whichever agent gave it.

    `cwd` is the worktree this review judges; passed as None when empty, since
    `Popen(cwd="")` raises rather than staying in the process's own directory.
    """
    from providers import claude  # late: providers imports this module at its foot
    out = claude(os.environ.get("GRAPH_CLAUDE", "claude"), prompt, account=resource.account,
                 model=resource.model, effort=effort or REVIEW_EFFORT,
                 allowed_tools=tools.READ, disallowed_tools=tools.READ_ONLY_DENIES,
                 read_only=True, timeout=timeout, cwd=cwd or None)
    if not out.ok:
        return out
    verdict, findings = _read_review(out.text or "")
    if verdict not in ("ACCEPT", "REJECT"):
        return Outcome("malformed", text=(out.text or "").strip()[:500], raw=out.raw,
                       cost=out.cost, tokens=out.tokens)
    return Outcome("ok", text=findings or out.text, verdict=verdict, raw=out.raw,
                   cost=out.cost, tokens=out.tokens)


def _one_review(binary: str, prompt: str, model: str, cwd: str, effort: str,
                timeout: int) -> Outcome:
    """One review call on one model, always read-only — a reviewer that can
    write can alter what it grades. `cwd` only moves where it reads from.

    The call itself is `provider_codex.codex_text`, which knows nothing about
    verdicts; only `_read_review` is the review's.
    """
    out = codex_text(binary, prompt, model=model, effort=effort or REVIEW_EFFORT,
                     cwd=cwd, timeout=timeout)
    if not out.ok:
        # The reviewer's own exit already said the call did not finish, so
        # whatever its output holds is not a verdict.
        return out
    verdict, findings = _read_review(out.text)
    if verdict not in ("ACCEPT", "REJECT"):
        # Only now do the words matter: a reviewer that answered is not a
        # reviewer that was refused, whatever its banner says about limits.
        return Outcome(_classify_text(out.raw) or "malformed",
                       text=(out.text or out.raw).strip()[:500], raw=out.raw)
    return Outcome("ok", text=findings or out.text, verdict=verdict, raw=out.raw)
