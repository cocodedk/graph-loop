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

## `--lanes auto`, and why it reads a rise and not a level

`--lanes N` is a cap and stays one. `--lanes auto [--lanes-max N]` hands the number
to a throttler instead: lanes in a turn are the smallest of the frontier's width, the
owner's ceiling, the keeper's three, and what the machine will take.

**It never raises, and that is a shape rather than a promise.** Every method the driver
calls goes through one door that catches everything, and the answer it falls back to is
arithmetic over numbers already in memory: no file, no `/proc`, no log — because that is
the only path left once everything else has failed. Saying that a fault happened is a
boundary like any other and is wrapped the same way; the line that said so once printed
outside the guard around it, which made a closed stdout the thing that killed the driver.
A throttler that kills a turn is worse than no throttler.

**A lane is added only on positive proof, and doubt resolves downward.** A turn earns
another lane only when THIS driver measured it in THIS turn: two whole readings at least
— an empty or half-read `/proc` is a broken reading, not a reading — the sampling thread
back in time, and nothing flagged. Everything else holds where it is. A cut needs no such
proof: what a reading saw, it saw, even if it stopped early.

It starts at the ceiling when one is given, because starting at one lane would
serialise cards the graph has just said are independent. With no ceiling it starts at
one lane and adds one per clean turn.

Signals are read at the start of a turn, with no lane running, and again every two
seconds while the lanes run: `MemAvailable` and swap from `/proc/meminfo`, `some
avg10` from each of `/proc/pressure/{cpu,memory,io}`. Each is optional — a platform
that does not have it reads as nothing rather than as zero.

Every judgement is a **rise over that turn's own baseline**, and that is the lesson
the measurements paid for: io pressure on the machine this was built on sat at 88–94 %
while it was idle and was *lower* under load. An absolute threshold would have
throttled it to one lane for ever, so io is recorded and never cut on.

A reader that dies under load leaves swap "unmoved" and pressure "flat" because nobody
looked. So does one that stalls past the end of its turn — it keeps its own buffer, its
own flag and its own stop, so whatever it finally says lands in the turn it belongs to
and never in the next one, and that turn counts as unmeasured.

What cuts, halving and holding still for two turns after: swap growing by more than
500 MB inside a turn — the only criterion that fired in the measurement, at three
lanes (1.1–1.3 GB) while every gate still passed; memory or cpu pressure more than 20
points over the baseline; a gate that PASSED taking more than 2.5 times the time the
same gate took alone — a gate that FAILED in a tenth of a second says nothing about how
long the work takes, and taken as a lone time it made the repaired gate read as a
hundredfold slowdown. What holds without cutting: swap that moved at all, and a turn where
`MemAvailable` minus a 3 GB reserve is below one lane's cost — about 2.6 GB on that
machine, measured from the first turn's drop, and assumed to be 2.5 GB until a turn
measures it.

Every decision is an event carrying its inputs: the width, each ceiling, the
baseline, the signals, the lanes chosen and the reason in words.

What it carries between turns lives in one file in the campaign directory, never in the
vault: the allowance, the turns it is holding still for, one lane's measured cost, and
the last turn's reading itself. The driver is killed and started again routinely, so a
cut a turn earned has to survive the process that earned it — and the reading is put on
the platter FIRST when a turn closes, before the gate timing, which is a nicety that
once took the reading down with it.

That file is read by a driver that did not write it and is never trusted. Every value is
made into the type it is read as, or dropped, so a state file of nonsense costs a dull
answer and never a dead driver; and a reading that comes back from it is marked as
carried, so the first decision after a restart can hold or cut, never climb.
