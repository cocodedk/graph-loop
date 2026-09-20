"""The criteria accepted before a build, kept through later planning repairs."""

from __future__ import annotations

from copy import deepcopy

FIELDS = ("goal", "gate", "done_when", "files")


def criteria(card: dict) -> dict:
    """Copy the grant; list order is not authority, and later edits cannot alias it."""
    result = {key: deepcopy(card.get(key)) for key in FIELDS}
    if isinstance(result["files"], list):
        result["files"] = sorted(result["files"])
    return result


def accepted_criteria(card: dict) -> dict | None:
    """Older accepted cards have only contract_seen; preserve their current grant."""
    saved = card.get("accepted_criteria")
    if saved is not None:
        return deepcopy(saved)
    return criteria(card) if card.get("contract_seen") else None


def changed_criteria(card: dict, proposed: dict) -> str:
    """A planning repair cannot turn an accepted task into different work."""
    saved = accepted_criteria(card)
    if saved is None:
        return ""
    effective = criteria({**card, **proposed})
    changed = [key for key in FIELDS if saved.get(key) != effective[key]]
    return ("this task's accepted criteria are fixed: " + ", ".join(changed)
            + "; record different work as a separate task") if changed else ""
