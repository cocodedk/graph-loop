"""The slicer's closed answer and the checks that run before any backlog write."""

from __future__ import annotations

import pathlib
import re

import yaml  # type: ignore[import-untyped]
from contract_paths import (  # noqa: F401 — contracts stays the door
    _inside,
    _sources,
    _strings,
)
from contract_task import _task
from slicer_law import (
    assert_one_owner,
    assert_order,
    assert_wall,
    available,
    lineage,
    signature,
)

RESULTS = {"MOLECULE", "NO_GAP", "NEEDS_PERSON"}
TOP = {"result", "reason", "molecule"}
BASE = {"name", "source", "goal", "why", "needs", "atoms"}
REQUIRED = {"goal", "files", "gate", "done_when"}
OPTIONAL = {"note", "needs", "uses", "creates", "gate_files_are_the_work",
            "gate_until_kept", "gate_when_kept",
            "gate_has_side_effects", "helper_verbs", "may_add_files", "expect_red"}
ATOM = REQUIRED | OPTIONAL | {"name", "stage"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


FENCE = re.compile(r"(?ms)^```[^\n]*\n(?P<inside>.*?)^```[ \t]*$")


def mapping(text: str) -> dict:
    """One YAML mapping, read from the first fenced block when there is one.

    It used to take the fence only when the fence was the whole answer, so a
    planner that wrote one line of preamble before its ```yaml lost a perfectly
    good answer to "the answer is not YAML" (2026-09-18). A model writes that
    line routinely and no instruction reliably stops it; reading the fence it
    did write costs nothing and refuses nothing that was ever valid, because a
    fenced block is not YAML at the top level anyway.
    """
    body = text.strip()
    fenced = FENCE.search(body)
    if fenced:
        body = fenced["inside"]
    try:
        loaded = yaml.safe_load(body)
    except yaml.YAMLError as error:
        raise ValueError(f"the answer is not YAML: {error}") from error
    if not isinstance(loaded, dict):
        raise ValueError("the answer is not a mapping")  # noqa: TRY004 — one refusal channel
    return loaded


def safe_name(value: object, what: str = "name") -> str:
    if not isinstance(value, str) or not SAFE_NAME.fullmatch(value):
        raise ValueError(f"{what} must contain only letters, numbers, dot, dash or underscore")
    return value


def validate(answer: dict, *, repo: pathlib.Path, sources: list[pathlib.Path],
             rows: list[dict], target: dict | None = None) -> dict:
    """Return a valid closed answer or raise without touching the backlog."""
    if target:
        assert_wall(target)
    _keys(answer, TOP, TOP, "answer")
    result = answer.get("result")
    if result not in RESULTS or not isinstance(answer.get("reason"), str):
        raise ValueError("result or reason is invalid")
    if result != "MOLECULE":
        if result == "NO_GAP" and target:
            raise ValueError("NO_GAP cannot close an unresolved target")
        if answer.get("molecule") is not None:
            raise ValueError(f"{result} requires molecule: null")
        return answer
    made = answer.get("molecule")
    if not isinstance(made, dict):
        raise ValueError("MOLECULE requires one molecule mapping")  # noqa: TRY004
    atoms = made.get("atoms")
    if not isinstance(atoms, list) or not all(isinstance(row, dict) for row in atoms):
        # T5 spent a repair round on a plan that simply left the key out: say
        # what to write, or the next answer guesses at the same wall
        raise ValueError("atoms must be a list of mappings — write `atoms: []` "
                         "when the molecule itself is the runnable task")
    # `note` is allowed at BOTH levels: the prompt asks for file boundaries in
    # it, the loop's own parents carry one, and refusing it burned the slicer
    # round that held T26.observation.read. It stays optional at the molecule
    # level — BASE is also the required set, so it cannot be added there.
    allowed = (BASE | {"note"}) if atoms else BASE | REQUIRED | OPTIONAL
    if atoms and "note" in made and not isinstance(made["note"], str):
        raise ValueError("note must be text")
    _keys(made, allowed, BASE | (REQUIRED if not atoms else set()), "molecule")
    name = safe_name(made.get("name"), "molecule name")
    if target and name.startswith(f"{str(target['id']).split('.')[0]}."):
        raise ValueError("a child molecule name cannot look like an atom in its parent's folder")
    _sources(made.get("source"), repo, sources)
    known = {str(row.get("id")) for row in rows}
    _strings(made.get("needs"), "molecule needs")
    if set(made.get("needs") or []) - known:
        raise ValueError("molecule needs names a task that does not exist")
    if target and target["id"] in (made.get("needs") or []):
        raise ValueError("a child molecule cannot wait on the leaf it replaces")
    leaves = atoms or [made]
    seen: set[str] = set()
    for atom in leaves:
        if atoms:
            _keys(atom, ATOM, REQUIRED | {"name", "stage"}, "atom")
            safe_name(atom.get("name"), "atom name")
            if atom["name"] in seen:
                raise ValueError(f"duplicate atom name: {atom['name']}")
            seen.add(atom["name"])
            if not isinstance(atom.get("stage"), int) or isinstance(atom.get("stage"), bool) \
                    or atom["stage"] < 1:
                raise ValueError("an atom stage must be a positive integer")
        _task(atom, repo, known)
    assert_order(name, made, rows, target)
    assert_one_owner(name, made, rows, target)
    available(leaves, repo)
    if target:
        old = {signature(row) for row in lineage(target, rows)}
        if any(signature(atom) in old for atom in leaves):
            raise ValueError("a new leaf repeats a failed ancestor contract")
        granted = set(target.get("files") or [])
        added = sorted(set(leaves[0]["files"]) - granted) if len(leaves) == 1 else []
        if added:
            # The rule stays — it is what stops a failed card's bad scope
            # becoming permanent (SLICER.md). The refusal names the answer,
            # because the one card this ever parked was re-sliced three times
            # and refused with the same sentence each round: widening the grant
            # is the repair a one-leaf rewrite would make, and it is the one
            # this forbids, so the planner has to be shown the other.
            raise ValueError(
                f"a one-leaf rewrite may not add a file: this card grants {sorted(granted)} "
                f"and this leaf adds {added}. Write two atoms instead — stage 1 whose files "
                f"are {added} and whose gate proves the work they must do, then stage 2 whose "
                f"files are {sorted(granted)} and which carries this gate.")
    return answer


def _keys(body: dict, allowed: set, required: set, what: str) -> None:
    extra, missing = set(body) - allowed, required - set(body)
    if extra or missing:
        raise ValueError(f"{what} keys are closed; extra={sorted(extra)}, missing={sorted(missing)}")
