"""Ask a decisions model about a molecule's cuts and atoms, and act on the answers by state."""

from __future__ import annotations

from typing import NamedTuple

import cut_questions
import cut_states
import cut_verdicts


class Checked(NamedTuple):
    molecule: object
    findings: list
    verdicts: list


def _ask_all(molecule, wall, ask) -> list:
    """Every verdict the model gave; a question whose ask fails or is not ok adds none."""
    verdicts = []
    for asked in cut_questions.for_cuts(molecule) + cut_questions.for_atoms(molecule, wall):
        try:
            answer = ask(asked.state, asked.questions)
        except Exception:
            continue
        verdicts += cut_verdicts.read(asked, answer)
    return verdicts


def check(molecule, campaign, space, ask, wall=None) -> Checked:
    """`space` is accepted and not interpreted: recording is the caller's wrapping of `ask`."""
    state = cut_states.load(campaign)
    if state not in ("observe", "act"):
        return Checked(molecule, [], [])
    verdicts = _ask_all(molecule, wall, ask)
    if state == "observe":
        return Checked(molecule, [], verdicts)
    pairs = cut_verdicts.merges(molecule, verdicts)
    # apply_merges renumbers the stages even for no pairs, so it only runs when there is a merge.
    merged = cut_verdicts.apply_merges(molecule, pairs) if pairs else molecule
    return Checked(merged, cut_verdicts.findings(molecule, verdicts), verdicts)
