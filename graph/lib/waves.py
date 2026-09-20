"""The frontier projected forward: the waves this backlog would run in.

Pure. Take what `startable` would offer, treat that wave as done, and ask
again — so the cards a wave releases are the next wave, and the shape of the
graph is what a person sees instead of a flat list of ids.

It is a SNAPSHOT and never a promise. The backlog is re-sliced between runs,
and a card that fails is parked for the next plan phase to cut differently, so
every line here is labelled as of the moment it was printed.

A held card is never scheduled: it is listed as held, and whatever waits
behind it waits with it. That is the same rule `startable` already keeps — the
hold is a person's decision and the loop does not schedule around it.
"""

from __future__ import annotations

from backlog_status import settled
from frontier import startable
from turn_plan import MOST_LANES


def project(rows: list[dict], running: list[str] | None = None) -> list[list[str]]:
    """The ids of each wave, in the order the loop would reach them.

    `running` is what another agent holds right now, so the first wave agrees
    with what the driver would actually be offered this moment.
    """
    left = [dict(row) for row in rows]      # a projection writes nothing back
    waves: list[list[str]] = []
    while True:
        wave = [str(row.get("id")) for row in startable(left, running)]
        if not wave:
            return waves
        waves.append(wave)
        taken = set(wave)
        for row in left:
            if str(row.get("id")) in taken:
                row["status"] = "done"      # treat it as done, and ask again
        running = None                      # whoever is running now has finished by then


def held(rows: list[dict]) -> list[str]:
    """Every card a person is holding that has not settled. Never scheduled,
    and named, so the reader knows why the graph stops where it does."""
    finished = settled(rows)
    return [str(row.get("id")) for row in rows
            if row.get("blocked_by_human") and row.get("id") not in finished]


def turns_for(width: int, cap: int) -> int:
    """How many turns a wave that wide takes at that cap."""
    return -(-width // cap) if cap > 0 else 0


def as_text(rows: list[dict], running: list[str] | None = None,
            cap: int = MOST_LANES) -> str:
    """The waves a person reads, labelled as of this moment."""
    waves = project(rows, running)
    lines = ["  waves from here, as the backlog stands now "
             + "(the next plan phase re-slices it, so this is a snapshot):"]
    if not waves:
        lines.append("    nothing can start from this backlog as it stands")
    for number, wave in enumerate(waves, 1):
        wider = (f" — {len(wave)} wide, cap {cap}, "
                 f"{turns_for(len(wave), cap)} turns" if len(wave) > cap else "")
        lines.append(f"    wave {number}: {', '.join(wave)}{wider}")
    holds = held(rows)
    if holds:
        lines.append(f"    held on the card, never scheduled: {', '.join(holds)}")
    return "\n".join(lines)


def say(rows: list[dict], running: list[str] | None = None,
        cap: int = MOST_LANES) -> None:
    print(as_text(rows, running, cap))
