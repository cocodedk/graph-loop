"""The deterministic TRIAGE signature table.

Each row names the incident that paid for it. Unknown is an honest result; the
bounded read-only model gets one chance later.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import re

from triage_evidence import Ending, has_outcome
from triage_stable import (
    stable,  # the scrub's home since the 200-line split; this stays its front door
)

VERDICTS = ("work", "contract", "gate", "rig", "environment", "harness", "unknown")
ENVIRONMENT = ("modulenotfounderror", "never came up", "ran 0 tests")
PATH = re.compile(r"(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|md|yaml|yml|json|sh)")
MISSING = re.compile(r"(?P<path>(?:\.?[\w.-]+/)*[\w.-]+): No such file or directory",
                     re.IGNORECASE)
REPEATED_ENDING = re.compile(
    r"^(?P<task>\S+) ended at .*?same way \d+ times:\s*(?P<said>.*?)"
    r"\s*(?:— the next turn.*)?$", re.DOTALL)


@dataclasses.dataclass(frozen=True)
class Decision:
    verdict: str
    signature: str
    why: str


def classify(ending: Ending) -> Decision | None:
    """Return the first matching row; order is part of the table."""
    events, card = ending.events, ending.card
    event_words = "\n".join(str(row.get("why") or "") for row in events)
    low = event_words.lower()
    kinds = {str(row.get("kind") or "") for row in events}

    if not has_outcome(ending):
        return None
    if "accepted" in kinds:
        return None

    # B4: provider trouble is the harness, whether before work or after it.
    if "review_unavailable" in kinds or "review did not happen" in low \
            or "builder's call went wrong" in low:
        return Decision("harness", "provider-fault", "a provider step did not happen")
    attempts = [row for row in events if row.get("kind") == "attempt"]
    if attempts and all(row.get("outcome") in ("limit", "auth", "capacity")
                        for row in attempts):
        return Decision("harness", "resource-unavailable",
                        "every resource refused before reading")

    people = [row for row in events if row.get("kind") == "needs_a_person"]
    if people:
        why = str(people[-1].get("why") or "the loop asked for a person")
        return Decision("unknown", "person-queued", why)

    refused = [row for row in events if row.get("kind") == "refused"]
    if any(row.get("step") == "red_first" for row in refused):
        output = _last(ending.artifacts.get("red-first")) or event_words
        if _environment(output, card):
            return Decision("environment", _environment_signature(output),
                            "the red-first gate did not run")
        return Decision("contract", "red-first", "the card's gate cannot prove red")
    if any(row.get("step") in ("contract", "scope_of_gate", "names") for row in refused):
        return Decision("contract", "contract-refused", "the contract was refused")

    if "quarantined" in kinds:
        return _quarantine(ending, event_words)

    failed_gate = any(row.get("kind") == "failed" and row.get("step") == "gate"
                      for row in events)
    if failed_gate:
        gate_output = _last(ending.artifacts.get("gate-output"))
        if gate_output is None:
            return Decision("unknown", "missing-gate-evidence",
                            "the gate failed but its artifact cannot be read")
        if not gate_output.strip():                         # T25 r1-r2
            return Decision("gate", "mute-gate", "the failing gate printed nothing")
        if _environment(gate_output, card):                    # T25 r3
            return Decision("environment", _environment_signature(gate_output),
                            "the scrubbed gate could not start its test rig")
        outside = _outside_path(gate_output, list(card.get("files") or []))
        if outside:
            return Decision("rig", f"outside-file:{outside}",
                            f"the failure names {outside}, outside this card")
        if _repeated(gate_output, ending.gate_outputs):
            digest = hashlib.sha256(stable(gate_output).encode()).hexdigest()[:12]
            return Decision("work", f"repeat-gate:{digest}",
                            "a speaking gate failed the same way twice")
        return Decision("unknown", "unmatched-gate", "the speaking gate failed once")

    if any(row.get("kind") == "failed" and row.get("step") == "scope" for row in events):
        # The fence says WHERE bytes landed, never whose fault that was, so this
        # row names no cause. Run 6 paid for it: two builders answered DONE with
        # every test green, left compiler output in a scratch directory the
        # sandbox would not let them remove, and the fence refused both cards.
        # Named `work`, that sent the slicer to rewrite two cards that were
        # right. The outside paths, the card's files and the builder's own
        # answer are all in the evidence; the model reads them, and `unknown`
        # requeues the card once meanwhile (`plan_phase.FAULTS`) instead of
        # recutting it.
        return Decision("unknown", "scope", "the builder wrote outside its files")
    if "rejected" in kinds or "rebuild_queued" in kinds:
        return Decision("work", "review-finding", "the work received a review finding")
    if card.get("status") == "refused_contract":
        return Decision("contract", "contract-refused", "the contract is refused")
    return Decision("unknown", "unmatched-ending", "no deterministic signature matched")


def _quarantine(ending: Ending, why: str) -> Decision:
    if "turns finished and nothing was accepted" in why:
        return Decision("harness", "campaign-futility",
                        "the watchdog parked a card for a campaign-wide symptom")
    found = REPEATED_ENDING.search(why)
    if found and found["task"] != ending.task:
        return Decision("harness", "watchdog-wrong-task",
                        f"the watchdog named {found['task']} but parked {ending.task}")
    said = ending.gate_outputs[-1] if ending.gate_outputs else (
        found["said"] if found else why)
    if _environment(said, ending.card):
        return Decision("environment", _environment_signature(said),
                        "the repeated ending did not run its gate")
    outside = _outside_path(said, list(ending.card.get("files") or []))
    if outside:
        return Decision("rig", f"outside-file:{outside}",
                        f"the repeated ending names {outside}, outside this card")
    if not said.strip():
        return Decision("gate", "mute-gate", "the repeated ending printed nothing")
    return Decision("work", "repeated-ending", "the repeated ending spoke")


def _environment(text: str, card: dict) -> bool:
    low = text.lower()
    if "the gate could not run (" in low:
        return True
    if not card.get("gate_has_side_effects") and any(mark in low for mark in ENVIRONMENT):
        return True
    if "command not found" in low:
        return True
    found = MISSING.search(text)
    return bool(found and not _belongs(found["path"], list(card.get("files") or [])))


def _environment_signature(text: str) -> str:
    return ("scrubbed-python" if any(mark in text.lower() for mark in ENVIRONMENT)
            else "missing-runtime")


def _last(rows: tuple[str, ...] | None) -> str | None:
    return rows[-1] if rows else None


def _repeated(output: str, history: tuple[str, ...]) -> bool:
    same = stable(output)
    return sum(stable(old) == same for old in history) >= 2


def _outside_path(output: str, allowed: list[str]) -> str:
    if not allowed:
        return ""
    for raw in PATH.findall(output):
        path = _task_path(raw)
        if not _belongs(str(path), allowed):
            return str(path)
    return ""


def _belongs(raw: str, allowed: list[str]) -> bool:
    path = _task_path(raw)
    return any(path == pathlib.PurePosixPath(name)
               or pathlib.PurePosixPath(name) in path.parents for name in allowed)


def _task_path(raw: str) -> pathlib.PurePosixPath:
    parts = pathlib.PurePosixPath(raw).parts
    task_at = next((i + 1 for i, part in enumerate(parts)
                    if part.startswith("task-")), 0)
    return pathlib.PurePosixPath(*parts[task_at:])
