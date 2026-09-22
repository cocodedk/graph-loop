"""One Markdown issue draft per stalled signature, assembled from the ledger.

No triage or provider is called. The card supplies its current status; the
ledger supplies the ending and its wide evidence. A digest of scrubbed words
names the draft. Each run appends each card once, and retains earlier runs.
"""

from __future__ import annotations

import hashlib

import durable
from backlog import Backlog
from campaign_of import backlog_of
from ending_reason import review_reason
from gate_reports import excerpt
from issue_scrub import identities, scrub
from triage_evidence import _read
from watchdog_spin import ENDINGS, current_run, ending_signature

PERSON = {"refused_contract", "rejected", "needs_slice", "quarantined",
          "partial_by_agent", "blocked_by_human", "lane_failed"}
CAUSES = ENDINGS + ("needs_a_person", "review_unavailable", "held")
ARTIFACTS = {"gate": "gate-output", "red_first": "red-first",
             "contract": "contract-answer", "diff_review": "diff-review-answer"}


def _evidence(space, rows: list[dict], card: dict) -> tuple[str, str]:
    own = [row for row in rows if row.get("task") == card["id"]]
    # A quarantine/rejection wraps the original ending. Keep its real step
    # and words rather than the watchdog's hundred-character summary.
    start = next((index + 1 for index in range(len(own) - 1, -1, -1)
                  if own[index].get("kind") == "claimed"), 0)
    own = own[start:]
    causes = [row for row in own if row.get("kind") in CAUSES]
    last = causes[-1] if causes else {}
    timed = next((row for row in reversed(own) if row.get("kind") == "step"), {})
    cause = (next((row for row in reversed(causes) if row.get("step")), last)
             if last.get("kind") == "rejected" else last)
    step = str(last.get("step") or cause.get("step") or timed.get("step")
               or last.get("kind") or "unrecorded")
    if last.get("kind") in ("held", "needs_a_person"):
        step = str(last.get("step") or {"held": "held", "needs_a_person": "build"}[last["kind"]])
    if step == "keep" and timed.get("clash"):
        step = "combined_gate"
    why = str(cause.get("why") or card.get("refused_why") or "")
    review = step in ("contract", "diff_review")
    if review:
        # A watchdog quarantine replaces the card's reason with its own
        # summary. The original review ending still owns the verdict.
        recorded = None if card.get("status") == "quarantined" else card.get("refused_why")
        why = review_reason(cause.get("why"), recorded)
    name = ARTIFACTS.get(step)
    if name:
        before = own[:own.index(last)] if last in own else []
        artifact = next((row for row in reversed(before)
                         if row.get("kind") == "artifact" and row.get("name") == name), {})
        text = _read(artifact.get("path"), space.root, tail=not review) or ""
        if review:
            # A raw answer may contain all the reviewed source. It never
            # displaces a recorded verdict, except to complete a cut event.
            why = review_reason(why, text) if not why or len(why) == 400 else why
        else:
            why = text or why
    return step, why or "No ending text was recorded."


def draft_stalls(space, book=None, *, repeated: str = "") -> None:
    """Called at stand-down, or just after the watchdog dealt with a spin."""
    if book is None:
        path = backlog_of(space)
        if not path:
            return
        book = Backlog(path)
    cards, rows = book.tasks(), space.events()
    run = current_run(rows)
    names = identities(rows, cards)
    seen = {(row.get("signature"), row.get("task")) for row in run
            if row.get("kind") == "issue_drafted"}
    run_number = sum(row.get("kind") == "driver_started" for row in rows)
    for card in cards:
        status = str(card.get("status") or "todo")
        if repeated:
            if card["id"] != repeated:
                continue
            rule = "watchdog: same ending twice; quarantine unless the card has already settled"
        elif status in PERSON or card.get("blocked_by_human"):
            rule = "driver stood down with a card needing a person"
        else:
            continue
        step, why = _evidence(space, rows, card)
        safe_step, safe_why = scrub(step, names), scrub(why, names)
        if step in ("gate", "red_first", "combined_gate"):
            safe_why = excerpt(safe_why)
        key = ending_signature({"step": safe_step, "why": safe_why})[1:]
        signature = "stall-" + hashlib.sha256(repr(key).encode()).hexdigest()[:20]
        if (signature, card["id"]) in seen:
            continue
        path = space.root / "issues" / f"{signature}.md"
        # A draft is an export, never a write through a link to somebody's file.
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("issue draft path is a symlink")
        previous = path.read_text("utf-8") if path.exists() else f"# Stall {signature}\n"
        marker = f"<!-- run {run_number}, card {hashlib.sha256(card['id'].encode()).hexdigest()[:20]} -->"
        if marker not in previous:
            held = "; blocked_by_human" if card.get("blocked_by_human") else ""
            section = (f"\n{marker}\n## Card {scrub(card['id'], names)}\n\n"
                       f"Loop step: {safe_step}\n\n"
                       "Refusal or gate text:\n\n" +
                       "\n".join("    " + line for line in safe_why.splitlines()) + "\n\n"
                       f"Run: {run_number}\nStatus: {scrub(status, names)}{held}\nRule: {rule}\n")
            durable.replace(path, previous + section, exclusive=True)
        space.event("issue_drafted", task=card["id"], signature=signature)
        seen.add((signature, card["id"]))
