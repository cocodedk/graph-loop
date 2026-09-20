# The graph loop — design

How to build this loop, anywhere. What each part is, why it exists, and the order that
makes it safe to leave alone. `DIARY.md` beside this file is the story of how it was
learned; this file is the design.

The runtime is here: `graph/` is the driver and `slicer/` is the planner. This document is
still written so that you could build the loop yourself without reading the code.

## The idea in one paragraph

A backlog of atomic tasks is worked to done by two models that never trust each other: a
reviewer refuses any task whose gate could pass without the work, a builder does one task
in a private worktree, the gate — a command whose exit code is the verdict — decides, the
reviewer reads the finished diff, and only then is the work committed to a campaign
branch. Everything the loop says, hears and measures is written to an append-only log, and
a watchdog reads that log to catch the loop going through the motions. A person is needed
only where a task says so, and the loop says out loud when it needs one.

## The parts, in dependency order

| part | one job |
|---|---|
| backlog | which task may start: dependencies met, files disjoint, humans respected |
| providers | call a model and read the answer honestly; a limit or a denial is never an attempt |
| gates | run a gate; the exit code decides; prove it red before anyone builds |
| workspace | the campaign's memory: rotating events, timed steps, artifacts, claims, alerts, the stop flag |
| worktree | one detached checkout per task; the scope check; the lock for tasks that touch shared state |
| distress | the builder's last line: JSON with fixed flags, or UNCLEAR and a person is told |
| loop | one task start to finish: held? → lock → red-first → contract review → build → scope → gate → diff review → keep |
| keep | accepted work becomes a commit on the campaign branch; the next task starts from that tip |
| watchdog | spinning, stuck, futile — read from the log, measured in time, never money |
| replan | a refused contract is rewritten from the reviewer's findings, twice at most, never wider |
| report | where the clock went, by step and by task; the bottleneck named |
| doctor | the mistakes already made, checked for after every task |
| view | the dashboard: warnings first, then the facts, all read from the log |
| slicer | the plan phase: turn a brief into branch goals, specs and every card, each reviewed |
| cardfile | the one reader and writer of a card's note; nothing else touches the file |
| triage | why an ending ended: the work, the machine, the rig or the gate |
| driver | init → approve → plan → run; status, report, doctor; stop and stop now |
| supervisor | restart a dead driver, back off on a crash loop, hourly report snapshots |
| window | clear, print the view, sleep |

## The card

A card is one note in a vault you can open in Obsidian. The note *is* the card: there is no
second copy and nothing is generated from anything, so what a person reads is byte for byte
what the loop reads. The vault lives in the repository being built, on the campaign branch,
so `git` is its history.

````markdown
---
status: todo                    # the picker offers only todo; the loop writes this field
files:                          # everything the gate can fail on, never what judges it
  - src/fetch.py
gate_files_are_the_work: true   # optional: writing the test IS the deliverable
gate_has_side_effects: true     # optional: the gate performs a live run — no red-first, take the lock
blocked_by_human: true          # optional: never started; shown as held
---

## Goal

one sentence, one idea

## Why

what it costs us that this is not done

## Done when

what the gate proves, and nothing more

## Gate

```sh
(cd tests && timeout 600 python3 -m unittest test_fetch)
```

## Needs

- [[T4/02-config-defaults]]

## Note

traps, the source of truth, what to do instead of guessing
````

The file is named number first, then the goal in a few words —
`04-signup-form-rejects-a-blank-email.md` — so the sidebar sorts in build order. `Needs`,
`Uses` and `Creates` are `[[wikilinks]]`, so Obsidian's graph view *is* the dependency
graph rather than a picture of one. Front matter holds what the loop decides; the body
holds what was written for a person, and the loop never touches it.

Gate rules: every path relative to the worktree; every stage in its own subshell
`(cd … && …)`; `set -o pipefail`; the verdict is the exit code; it must fail today for the
reason the task exists.

## Relatives: memory and learning around a card

A card is never edited to remember something. What is decided, tried or learned about a
node — a molecule, an atom, a root-level note — goes in a **relative**: a separate note
that links to the node instead. Obsidian then shows the relative as the node's neighbour in
its graph and its backlinks, while the node stays byte for byte what it was, which is what
keeps a card safe to have open while the loop runs.

Three kinds, told apart by the first word of the file name:

| kind | file name | how many | holds |
|---|---|---|---|
| memory | `memory-<node>.md` | one per node, append-only, dated sections | what was decided, tried and measured — it **points to the evidence and never copies it**, so the log stays the one home of the raw record and "nothing is written down twice" stays true |
| learning | `learning-<node>-<slug>.md` | one per learning | front matter `status: open\|adopted\|rejected`, `applies_to`, `basis: measured\|source\|design` |
| evaluation | `evaluation-<scope>.md` | one, written when the project is done | every open learning, read against the logs and marked adopted or rejected; an adopted one becomes a change to the method |

Relatives live in a `relatives/` folder: `<vault>/<Molecule>/relatives/` for a molecule and
its atoms, `<vault>/relatives/` for a root-level note. Never pre-create a molecule folder
to hold one — the slicer renames a finished molecule into place and refuses a name that
already exists.

And never put a relative **beside a card**. `molecule.ordered` reads every `.md` file in a
molecule's folder as an atom except `molecule.md` itself, and a name it cannot read as
`NN-stem.md` stops the whole read — one stray note beside the atoms breaks every card the
picker was about to offer, not just its own. A sub-folder is skipped rather than read as an
atom, which is why relatives live in one.

A relative has a card's shape — front matter, then `## ` sections — so the loop can read it
later without learning a second format.

### `remember`: the memory relative, written from the log

`graph-goal.py remember` is the one thing that writes a relative, and it is a command, not
a step: it is run by hand after a driver has stopped, and nothing on the loop's own path —
`run`, the driver, the supervisor, a hook — reaches it. It reads the campaign's log and the
backlog and writes, for every card, `<backlog>/<Molecule>/relatives/memory-<card>.md`
(`memory-molecule.md` for the molecule itself): front matter `kind: memory` and `node:` a
wikilink the vault resolves, a `## Node` list, then one dated `## ` section per thing that
happened — planned, each attempt with how it ended, each refusal, each gate run with its
exit code and its seconds, the keep with its commit.

It points and never copies. A section carries the event's time, the numbers and the *name*
of the numbered artifact file — `calls/<card>/003-contract-answer.txt` — never the
reviewer's words, never what the gate printed, never the absolute path the log records,
which names the machine the campaign ran on. The log stays the one home of the raw record.

The note is a projection: the same log gives the same bytes, so running the command twice
writes nothing and a note thrown away is rebuilt exactly. It never touches the card, not
even its front matter, and after it `backlog_tree.read` returns what it returned before.
An event it cannot make sense of is counted and stepped over — the counts are printed —
because a memory note is worth less than the campaign it describes.

**Two hands write in a memory note, and one rule tells them apart: every heading the
command writes ends with ` — from the log`.** Any other `## ` section is a person's own,
and comes back byte for byte, at the place in the file they put it — its index among the
sections, which holds because the log only ever grows at the end. The one thing to know
before writing in one by hand: do not end your own heading with that phrase, or the next
run will take the section over as its own.

The loop still does not *read* relatives, and no builder's or reviewer's prompt is fed one.
A card's `status` stays in the card's own front matter, where the loop writes it today.

## Two phases that never mix

Planning and building are separate commands. `graph-goal.py plan` slices until the backlog
stops changing and builds nothing; `graph-goal.py run` builds the cards and writes none.
A card that fails is parked, and the next plan phase is what re-slices it — so a driver
that has nothing startable hands back to the supervisor rather than waiting.

## The order of one task, and why each step is where it is

1. **held?** — a human hold is checked before anything costs money.
2. **lock** — a task that performs a live run takes it; only one at a time.
3. **gate ownership** — a builder that may edit the test judging it is refused before a
   review is paid for, unless the task declares the test is the work.
4. **prove red** — a gate that has never failed proves nothing; skipped only when the gate
   itself performs the work.
5. **contract review** — the reviewer reads the task, not the code; most defects die here
   at the price of one review.
6. **build** — one builder, one task, one worktree; the builder ends with one JSON line of
   fixed flags.
7. **flags** — BLOCKED and PARTIAL are believed: the worktree is kept, an alert is raised,
   a person is told. UNCLEAR alerts but the gate still judges.
8. **scope** — anything written outside the task's files refuses the work; the leavings of
   running a gate are not edits.
9. **gate** — the exit code decides. One failure leaves the task open; the second identical
   failure marks it for re-slicing.
10. **diff review** — a fresh reviewer reads the change with the goal in hand.
11. **keep** — commit on the campaign branch; the next worktree is cut from that tip, never
    from a HEAD that predates its dependency.
12. **doctor** — after every task, the loop checks itself for the mistakes it has already
    made, and writes what it finds where the dashboard shows it first.

Every ending writes a status the picker will not re-offer; every step is timed; every
prompt, answer, diff and gate output is a numbered file under the campaign's log.

## What it refuses to do

- Escalate effort. A failed gate means the task is wrong, not the model too small.
- Count a usage limit, a denial, a killed reviewer or malformed output as failure.
- Stop the campaign for one bad task — it quarantines and carries on. It stops itself only
  for hours of work with nothing accepted.
- Touch the main branch, force-push, or start anything a human holds.
- Trust its own memory: everything is re-read from files, so any part can be killed and
  restarted at any time.

## Atomising the work is the real job

It is a method, not a feeling:

1. Write the end state as gates first — commands that fail today and whose exit code will
   say the work is done. No task exists before its gate does.
2. One idea per task. If describing it needs the word "and", it is two.
3. The file list is everything the gate can fail on — counts, fixtures, pinned digests,
   sibling copies — and never the test that judges it, unless writing that test is the
   declared deliverable.
4. Dependencies are only what is real: a task waits for another only if it reads that
   task's output. Measure the backlog by what is startable now; a long chain behind one
   brick is a stalled weekend.
5. Mark what performs live actions, what writes its own proof, and what a person must see
   first.
6. Let the reviewer refuse your contracts cheaply before any building — one campaign's
   nine zero-cost refusals were the backlog being debugged, not the models failing.
7. Expect to re-slice: anything a builder cannot finish in about half an hour is too big,
   and two identical gate failures mean the task is wrong, not the model.

## What the numbers said

A pilot on a throwaway file: three contract refusals at $0, then one task end to end in
105 seconds for $0.19. The first real campaign: nine tasks refused at $0 — the backlog was
the defect, not the models. After the gates were rewritten to prove behaviour, the first
accepted commit was a specification that disagreed with the fixture it was generated from;
the builder found the specification wrong, added exactly the missing rows, and left the
fixture untouched.

Reviews are 70–99% of the clock. That is the price of refusing early, and the lever for
speed is better task contracts, not faster builders.

## Two things this design got wrong, kept here on purpose

**It claimed the logic was generic.** It was not. Four places in the source named the work
it was built for, one of them by copying a private directory into every worktree it
created. A claim of genericness is a measurement, not a statement. Those four are
configuration now — `GRAPH_REPO`, `GRAPH_HELPER`, `GRAPH_PROVISION_COPY` and
`GRAPH_PROVISION_LINK` — and the measurement is still a grep of the source.

**It described what the loop does and not how it is run.** The runner is the supervisor,
not the driver, and a campaign lasts days. Any front end for this loop has to start the
supervisor and return, then read its state from the log — never hold a session open
waiting for a campaign to end.
