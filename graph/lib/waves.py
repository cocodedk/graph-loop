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

from backlog_status import runs_alone, settled
from frontier import startable
from turn_plan import MOST_LANES


def project(rows: list[dict], running: list[str] | None = None) -> list[list[dict]]:
    """The cards of each wave, in the order the loop would reach them.

    Copies, so a projection writes nothing back through them. `running` is what
    another agent holds right now, so the first wave agrees with what the
    driver would actually be offered this moment.
    """
    left = [dict(row) for row in rows]      # a projection writes nothing back
    waves: list[list[dict]] = []
    while True:
        wave = startable(left, running)
        if not wave:
            return waves
        waves.append([dict(row) for row in wave])   # before they are marked done
        taken = {str(row.get("id")) for row in wave}
        for row in left:
            if str(row.get("id")) in taken:
                row["status"] = "done"      # treat it as done, and ask again
        running = None                      # whoever is running now has finished by then


def ids(wave: list[dict]) -> list[str]:
    return [str(row.get("id")) for row in wave]


def held(rows: list[dict]) -> list[str]:
    """Every card a person is holding that has not settled. Never scheduled,
    and named, so the reader knows why the graph stops where it does."""
    finished = settled(rows)
    return [str(row.get("id")) for row in rows
            if row.get("blocked_by_human") and row.get("id") not in finished]


def alone_in(wave: list[dict]) -> int:
    """How many of these cards the driver runs by themselves: a live card acts
    on the one shared stack, and a no-files evidence card has no edit for a
    lane to build (`backlog_status.runs_alone`)."""
    return sum(1 for row in wave if runs_alone(row))


def turns_for(wave: list[dict], cap: int) -> int:
    """How many turns this wave costs the loop.

    One turn each for the cards that run alone, and the rest packed into
    lanes. Dividing the whole wave by the cap said four independent live cards
    were two turns; the driver needs four.
    """
    alone = alone_in(wave)
    together = len(wave) - alone
    return alone + (-(-together // cap) if together and cap > 0 else 0)


def as_text(rows: list[dict], running: list[str] | None = None,
            cap: int = MOST_LANES) -> str:
    """The waves a person reads, labelled as of this moment."""
    waves = project(rows, running)
    lines = ["  waves from here, as the backlog stands now "
             + "(the next plan phase re-slices it, so this is a snapshot):"]
    if not waves:
        lines.append("    nothing can start from this backlog as it stands")
    for number, wave in enumerate(waves, 1):
        turns, alone = turns_for(wave, cap), alone_in(wave)
        # Said whenever the wave costs more than one turn, not only when it is
        # wider than the cap: two cards that each run alone are two turns at
        # any cap at all.
        cost = (f" — {len(wave)} wide, cap {cap}, {turns} turns"
                + (f" ({alone} run alone)" if alone else "") if turns > 1 else "")
        lines.append(f"    wave {number}: {', '.join(ids(wave))}{cost}")
    holds = held(rows)
    if holds:
        lines.append(f"    held on the card, never scheduled: {', '.join(holds)}")
    return "\n".join(lines)


def say(rows: list[dict], running: list[str] | None = None,
        cap: int = MOST_LANES) -> None:
    print(as_text(rows, running, cap))
