"""Ask a decisions model about a molecule's cuts and atoms, and act on the answers by state."""

from __future__ import annotations

import time
from typing import NamedTuple

import cut_questions
import cut_states
import cut_verdicts


class Checked(NamedTuple):
    """`requests` and `seconds` count only the calls to `ask`; `merges` counts the joins made."""
    molecule: object
    findings: list
    verdicts: list
    mode: str = ""
    requests: int = 0
    seconds: float = 0.0
    merges: int = 0

    @property
    def usable(self) -> int:
        return sum(1 for verdict in self.verdicts if verdict.usable)


def _ask_all(molecule, wall, ask) -> tuple[list, int, float]:
    """The verdicts, the requests sent and the seconds spent inside them.

    A question whose ask fails or is not ok adds no verdict, but it was still a request.
    """
    verdicts, requests, seconds = [], 0, 0.0
    for asked in cut_questions.for_cuts(molecule) + cut_questions.for_atoms(molecule, wall):
        requests += 1
        began = time.monotonic()
        try:
            answer = ask(asked.state, asked.questions)
        except Exception:
            continue
        finally:
            seconds += time.monotonic() - began
        verdicts += cut_verdicts.read(asked, answer)
    return verdicts, requests, round(seconds, 3)


def check(molecule, campaign, space, ask, wall=None) -> Checked:
    """`space` is accepted and not interpreted: recording is the caller's wrapping of `ask`."""
    state = cut_states.load(campaign)
    if state not in ("observe", "act"):
        return Checked(molecule, [], [], "off")
    verdicts, requests, seconds = _ask_all(molecule, wall, ask)
    if state == "observe":
        return Checked(molecule, [], verdicts, state, requests, seconds)
    pairs = cut_verdicts.merges(molecule, verdicts)
    # apply_merges renumbers the stages even for no pairs, so it only runs when there is a merge.
    merged = cut_verdicts.apply_merges(molecule, pairs) if pairs else molecule
    return Checked(merged, cut_verdicts.findings(molecule, verdicts), verdicts,
                   state, requests, seconds, len(pairs))
