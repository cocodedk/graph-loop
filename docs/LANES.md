# The frontier, and the lanes that follow it

How wide the graph is at any moment, how many lanes the loop gives it, and how to see
both. Split out of `DESIGN.md`, which stays under the repository's per-file limit and
points here.

The purpose of the graph is to assign a new agent each time it branches out, as many as
there are branches. The loop already does the running — one thread per startable card, up
to a cap — and what it lacked was the view.

`waves` is one pure function over the cards. It takes what the picker would offer,
treats that wave as done, and asks again; the cards a wave releases are the next wave.
`plan` prints it when it finishes and `status` prints it whenever you ask, and both label
it as of that moment: the backlog is re-sliced between runs, so a projection is a
snapshot and never a promise. A held card is listed as held and never scheduled — the
hold is a person's decision, and the loop does not schedule around it. Where a wave
costs the loop more than one turn, the same line says how wide it is, what the cap is
and how many turns it takes — counted the way the driver spends them, one turn each for
the cards that run alone (a live card, a no-files evidence card) and the rest packed
into lanes. Dividing the whole wave by the cap called four independent live cards two
turns; the driver needs four.

Each turn writes the three numbers down as well: the width the graph offered, the cap
the picker applied, and the lanes it ran. `report` reads them back and names the turns
where the graph was wider than the loop, which is the only honest way to say whether the
cap is costing anything. The cap itself is the keeper's: it rebuilds a commit whose
branch moved under it three times before it gives up, so a fourth lane would turn
ordinary branch movement into a lane failure. `--lanes N` lowers it and never raises it.

