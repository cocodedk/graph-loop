"""Read a decisions model's verdicts on a molecule and say what follows from them, pure."""

from __future__ import annotations

import copy
from typing import NamedTuple

import cut_questions


class Verdict(NamedTuple):
    id: str
    question: str
    choice: str
    confidence: object
    usable: bool


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def read(asked: object, answer: object, gate: float = 0.6) -> list[Verdict]:
    """One verdict per asked question that has an answer; none when the answer is not ok."""
    if not getattr(answer, "ok", False):
        return []
    given = getattr(answer, "answers", None)
    questions = getattr(asked, "questions", None)
    if not isinstance(given, dict) or not isinstance(questions, dict):
        return []
    out = []
    for question in questions:
        one = given.get(question)
        if not isinstance(one, dict):
            continue
        confidence = one.get("confidence")
        out.append(Verdict(str(getattr(asked, "id", "")), str(question), str(one.get("choice")),
                           confidence, _number(confidence) and confidence >= gate))
    return out


def _atoms(molecule: object) -> list[dict]:
    atoms = molecule.get("atoms") if isinstance(molecule, dict) else None
    rows = [a for a in atoms if isinstance(a, dict)] if isinstance(atoms, list) else []
    return sorted(rows, key=lambda a: a["stage"] if _number(a.get("stage")) else 0)


def _files(atom: dict) -> set:
    files = atom.get("files")
    return set(files) if isinstance(files, list) else set()


def merges(molecule: object, verdicts: list[Verdict]) -> list[tuple[str, str]]:
    """Adjacent atoms a usable `keep_together` on `cut` joins, when they share a file."""
    atoms = _atoms(molecule)
    keep = [v.id for v in verdicts if v.usable and v.question == "cut" and v.choice == "keep_together"]
    pairs = []
    for first, second in zip(atoms, atoms[1:]):
        one, two = first.get("name"), second.get("name")
        if not (isinstance(one, str) and isinstance(two, str) and one and two):
            continue
        if cut_questions._cut_id(one, two) in keep and _files(first) & _files(second):
            pairs.append((one, two))
    return pairs


def findings(molecule: object, verdicts: list[Verdict]) -> list[str]:
    """One sentence per usable `fail`, naming the atom whose id, `atom:<name>`, is the verdict id."""
    names = [a["name"] for a in _atoms(molecule) if isinstance(a.get("name"), str) and a["name"]]
    out = []
    for v in verdicts:
        if not (v.usable and v.choice == "fail"):
            continue
        named = [n for n in names if v.id == f"atom:{n}"]
        if named:
            out.append(f"Atom {named[0]} fails the question {v.question}.")
    return out


def _join(one: object, two: object) -> str:
    return "\n".join(str(x) for x in (one, two) if x)


def _root(absorbed: dict, name: object) -> object:
    """The atom a name ended up inside, after any number of merges."""
    while name in absorbed:
        name = absorbed[name]
    return name


def apply_merges(molecule: object, pairs: list[tuple[str, str]]) -> object:
    """A copy with each second atom joined into its first, the stages renumbered from 1."""
    if not isinstance(molecule, dict):
        return molecule
    made = copy.deepcopy(molecule)
    atoms = _atoms(made)
    by_name = {a.get("name"): a for a in atoms}
    absorbed: dict = {}
    for first, second in pairs:
        first, second = _root(absorbed, first), _root(absorbed, second)
        one, two = by_name.get(first), by_name.get(second)
        if one is None or two is None or one is two:
            continue
        one["files"] = sorted(_files(one) | _files(two))
        for key in ("goal", "done_when", "gate"):
            one[key] = _join(one.get(key), two.get(key))
        absorbed[second] = first
    kept = [a for a in atoms if a.get("name") not in absorbed]
    for number, atom in enumerate(kept, 1):
        atom["stage"] = number
    made["atoms"] = kept
    return made
