# The slicer loop — what was agreed (2026-08-31, recovered from the morning session)

The problem it exists to fix: cards are bad because a person writes them by
hand, from memory. Four expensive mistakes in one day were the same mistake —
a card naming a thing whose writer nobody had read (`observation`, `gpt-5.6`,
`OBSERVATION_RECORDED`, `CAPTURE_RECORDED`).

## Agreed

- **A slicer loop reads the specs** (`simulation/spec/**`, which are canon)
  **and the code**, and emits **molecules** — a subfolder per coherent piece of
  work — each holding **atoms**, one card apiece: one idea, one gate, no
  dependency unless real. The format is `lib/backlog_tree.py`, already landed:
  `molecule.md` is the parent card, the number in a file name is the stage.
- **The drive loop consumes atoms and builds them.** It stops authoring work
  entirely; the commander stops hand-writing cards.
- **The drive loop's contract review is the slicer's gate.** It already
  refuses a bad card for free, before any build. A refused atom goes back to
  the slicer with the finding, and the slicer — never a person — rewrites it.
  Red-first discipline, one level up.
- **Two triggers, one reader.** (a) No code yet: a spec declares what nothing
  implements; the slicer sees the gap and emits a molecule in buildable order.
  (b) A refused card: the slicer reads the refusal, the card and the code, and
  rewrites that one atom. In both cases it reads spec AND code — reading the
  code is never optional.
- **The slicer's law** (landed as the naming law, `lib/molecule.py`): every
  name an atom uses must exist in the repository, or the atom that creates it
  must come first in its molecule.
- **Folder per molecule** — decided in the same conversation.
- **The slicer is part of the loop, not the supervisor.** Slicing needs the
  backlog lock, the campaign log, the claims and the resource belt, which live
  inside the driver; a supervisor that slices is a second driver with no
  safeguards. The supervisor only keeps the loop alive and fed.

## Questions this plan resolves

The plan below resolves these:

- When the slicer runs: a standing loop of its own, or a step at the top of
  the driver's turn (where `replan_pending` sits today).
- Which model and effort slice, off the belt.
- The order of landing: the tree cutover (`where.backlog()` naming a folder)
  comes first; the slicer writes into that format.

Status before this plan: format landed and inert; slicer unbuilt. The plan and
specification below are the approval artifact; they do not authorise code by
themselves.

## Implementation boundary

the owner's 2026-08-31 instruction freezes the existing driver loop. The first
implementation MUST live in its own git worktree, add no change to existing
driver source, and emit the tree format the unchanged driver already reads. The
unchanged driver then tests the result on a small fictive project.

The top-of-turn call below remains the target design. Under this freeze — lifted
by the dated record just below — it was an integration impediment, not permission
to edit `drive-goal.py`, `lib/turn.py` or another existing driver file.

FREEZE LIFTED (the owner, 2026-09-01, in session: "when shall we integrate the
slicer? I want it integrated before we start on the triage" — delegation of
review standing since 2026-08-31). The acceptance review passed; integration
proceeds as reviewed bricks: modules merged, per-step trace, the tree cutover at
the next turn boundary, and the top-of-turn call in `lib/turn.py`.

A speccer is added only if the vertical test proves it is needed to turn an Alpha
goal into an approved source the slicer can read. If added, it uses the same
resource belt, and the first complete proof is one narrow path:

`goal → spec → molecule → atom → unchanged drive → gate`.

## Plan

The slicer has one job: keep the drive loop supplied with buildable work from
approved sources. It plans work; the drive loop still proves, reviews, builds,
keeps and records it.

1. Record the campaign's source paths at `init`. For this campaign they are
   under `simulation/spec/`, but the slicer receives paths; it does not compile
   that directory into its code.
2. Put one `slice_pending` step at the top of a driver turn, beside the current
   contract replan. It handles at most one planning need per turn. There is no
   second daemon and nothing new in the supervisor.
3. Reuse the planner belt at medium effort. Give the planner read-only access to
   the approved specs, the repository, the target card and its recorded failure.
   It may read and search; it may not write, run shell, call the stack or launch
   another agent.
4. Reuse the tree backlog. A new gap becomes one molecule. A leaf that has hit a
   wall becomes the parent of one smaller child molecule. That molecule holds
   the replacement atoms. `sliced_from` is the whole lineage; there is no
   subatomic task type and no depth limit.
5. Validate the complete answer before writing any of it. Then create the child
   molecule as a hidden folder, rename it into place, and mark the old leaf
   `sliced` last. A crash therefore leaves the old task parked, never half a
   molecule offered to a lane.
6. Send every new atom through the drive loop unchanged: naming law, contract
   review, red-first, builder, gate, independent diff review and keep. A
   slicer-written CODE gate is reviewed before it is first run. LIVE authority
   is copied only from its parent or an explicit commander-approved live
   contract. A specification declares behaviour; it does not authorise a live
   action.
7. Add the smallest tests for the new transition, assert their count, run the
   drive suite and the linter on touched code. An independent reviewer checks each
   implementation fixpoint before it is committed.

Implementation order:

1. Make the tree derive a sliced parent's children from `sliced_from`, including
   a child molecule of an atom, and prove recursive settlement.
2. Add one slicer function: gather evidence, make one read-only planning call,
   parse a closed YAML shape, validate it and publish one molecule.
3. Prove the unchanged driver reads and can run the generated backlog. Record
   the missing top-of-turn call as an impediment; do not add it under the freeze.
4. Add source-gap creation and the final independent coverage review. Update
   `BLUEPRINT.md` only after the freeze is lifted; no compatibility layer or
   second backlog format.

## Review of the plan

The Ponytail ladder was applied after tracing the real flow. The need is real:
hand-written cards have named absent fields and events, and the present loop can
park a leaf but cannot create its successor. Most of the solution already
exists, so the plan keeps it.

| Question | Decision |
|---|---|
| A separate slicer loop? | No. One step in `turn_opens` has the lock, log and resource belt already. |
| A `subatom` schema or nested atom folders? | No. A child molecule contains ordinary atoms and points back with `sliced_from`. Recursion gives all needed depth. |
| Rewrite a live molecule in place? | No. Publish a complete child folder, then change one parent status. This is the smallest safe multi-file write. |
| Force every child to stay inside the failed card's file list? | No. A rewrite stays inside it; a true slice may add one separately reviewed prerequisite atom when the cited source proves another file is required. Otherwise the original bad scope becomes permanent. |
| Cap slice depth or atom count? | No. Reject an unchanged ancestor contract instead. A fixed cap would recreate the wall this component exists to remove. |
| Let contract review prove the source is fully covered? | No. It can judge emitted atoms but cannot see an omitted one. One independent coverage review is required only when the slicer says no gap remains. |
| Add another parser, queue or resource list? | No. Use YAML, backlog order, `resources.belt("plan")` and the campaign log already present. |

Review result: the minimum design is one top-of-turn transition, one closed
answer shape and one recursive relation. The only extra guard is the closing
coverage review; without it the planner would grade its own completeness.

## Specification

### 0. What comes before it (2026-09-18)

Three writers stand above the slicer, and each one stops when its own piece is
written. Nothing in this chain builds, and nothing in it runs during a build
phase.

1. **The branch writer** (`slicer/branches.py`) turns one project brief into
   the branches a campaign is planned from. A branch is one capability a person
   would name, and the test for where its boundary lies is: **can this branch's
   acceptance be observed with the other branches absent?** If yes it is a
   branch; if no it belongs to the branch beside it. It writes acceptance in
   words and never a gate, one `NN-name.md` note per branch, whole or not at
   all. An independent reviewer refuses a branch nobody can observe, two
   capabilities in one branch, an invented fact or authority the brief does not
   grant.
2. **The speccer** (`slicer/speccer.py`) turns ONE branch goal into one small
   source spec, written as a note in the same vault and linked back to its
   branch (`--branch`). The graph has no root without that link.
3. **The slicer** turns specs into molecules and atoms, below.

Branch, then spec, then cards: each layer is a vault note, and the wikilinks
between them are the graph. The whole chain runs in the PLAN PHASE, with the
driver stopped (§ 3).

### 1. Scope

The slicer MUST:

- turn an uncovered claim in an approved source into one molecule;
- repair a refused CODE atom while the existing replan rounds remain;
- replace a CODE leaf that has hit a wall with a smaller child molecule; and
- return control so other startable atoms continue.

It MUST NOT build code, run a gate, commit, drop work, mark work done, broaden
LIVE authority or run in the supervisor.

### 2. The one recursive shape

- A molecule is one coherent outcome and one directory.
- `molecule.md` is its parent card. If the work is already atomic, this card is
  also the runnable atom and there are no numbered files.
- If it needs pieces, the parent is `sliced` and each runnable leaf is an
  `NN-name.md` atom. Lower numbers run first; equal numbers may run together.
- Re-slicing any runnable leaf creates a new molecule whose `molecule.md`
  names that leaf in `sliced_from`. The child inherits the leaf's external
  prerequisites but never waits on the leaf itself. The old leaf becomes
  `sliced` only after the new molecule exists.
- The backlog derives every parent-to-child wait from `sliced_from`. The normal
  `settled()` recursion releases the old leaf, its molecule and all downstream
  work only after every descendant settles.
- “Subatomic” means only “an atom in a child molecule”. It adds no file type,
  status or scheduler rule.

IDs are derived from directory and file names, as they are now. A new molecule
ID and every atom name MUST be unique, stable, path-safe and chosen from their
purpose, not from a retry count alone.

### 3. When it runs

In the PLAN PHASE, and never in a build turn. `drive-goal.py plan` runs the
slicer until the graph stops growing and builds nothing; `drive-goal.py run`
builds and writes no cards. They alternate and never overlap — this used to run
at the top of each driver turn, which is the two phases mixed by construction.

Each round of a plan phase takes, in backlog order:

1. the first eligible CODE leaf that the shared backlog status rule says has hit
   a wall; or
2. when nothing is startable, one molecule for the next uncovered claim in the
   approved sources.

A build turn still rewrites at most one refused CODE contract in place, which is
a repair of a card already written rather than a plan for new work.

A wall includes the existing terminal task-shape cases: repeated gate failure,
spent rebuild rounds, spent contract replans, an unprovable or already-green
gate, and quarantine for the same ending. One shared predicate MUST define this
for the picker, slicer, doctor and board.

A human hold, a LIVE call whose outcome is in doubt, a provider outage and a
harness fault are not task-shape evidence and MUST NOT be sliced. They do not
stop unrelated atoms or unrelated source gaps from being considered.

### 4. What the planner reads

For a source gap it reads the campaign goal, approved source paths, current
molecules and the repository at the campaign branch tip. For a wall it also
reads the target, its ancestors, every recorded finding and gate output, and the
kept worktree as prior art. The child notes carry those findings and that path,
but a child starts fresh and never resumes its parent's model session.

The planner uses `resources.belt("plan")` at medium effort with only read and
search tools. Every call uses the existing attempt, step and artifact records.
A resource refusal changes no task state.

### 5. Closed answer

The planner returns YAML with exactly these top-level fields:

```yaml
result: MOLECULE | NO_GAP | NEEDS_PERSON
reason: plain sentence
molecule: null | { ... }
```

`MOLECULE` carries one molecule with required `name`, `source`, `goal`,
`why`, `needs` and `atoms`. `source` is a non-empty list of exact
`repo/path:line` anchors under the approved source paths. `note` is optional at
BOTH levels — molecule and atom — and is text: the prompt asks for file
boundaries in it, and the loop's own parent cards carry one.

When `atoms` is empty, the molecule is the runnable atom: it also requires
`files`, `gate` and `done_when`, and may carry the normal optional task fields.
When `atoms` is not empty, each atom requires `name`, `stage`, `goal`, `files`,
`gate` and `done_when`; `note`, `needs`, `uses`, `creates` and the existing gate
flags are optional. No other fields are accepted. The writer, never the model,
supplies IDs, status, `sliced_from`, retry state and derived internal
dependencies.

`NO_GAP` requires `molecule: null` and triggers one independent coverage review
against the approved sources and existing molecules. It closes source slicing
only when that reviewer accepts. The campaign records that acceptance with the
source content digest, reuses it after restart, and discards it when a source
changes. `NEEDS_PERSON` also requires `molecule: null` and is valid only for
missing source authority or missing commander-approved LIVE authority; its
reason is shown as an alert while unrelated work continues.

Amended 2026-09-08 (astra's section H 5, under the owner's order that the loop never
waits for a person): a `NEEDS_PERSON` about the SOURCE GAP, and the cap on its
answered failures, no longer wait for a new declaration. The stop stands
(`lib/source_gap.py`): declaring a source opens a new window — no
`sources_declared` is ever fabricated — and a campaign that gets none ends with
its gaps recorded (`ended_with_gaps`, exit 78), which is not coverage and is
never reported as coverage. Amended again 2026-09-18, when the decider was cut:
its requeue used to buy one more attempt on the same sources, and there is no
such buyer now. A `NEEDS_PERSON` about a TARGET
still holds that card, and the card predicate decides it like any other.

### 6. Validation before write

The slicer treats the answer as untrusted input and MUST reject it without
changing the backlog unless all of these hold:

- the YAML is a closed shape with the result-specific fields above;
- names and paths cannot escape the backlog or repository;
- every source anchor exists inside an approved source path;
- every runnable root or numbered atom has one idea and a complete normal task
  contract, and every numbered atom has a positive integer stage;
- every `uses` name exists in the branch or is made by a lower-stage atom,
  using the existing molecule naming law; an atom at the same stage runs in
  parallel and licenses nothing;
- internal order has no cycle and every external `needs` ID exists;
- a rewrite adds no file; a wider prerequisite is its own atom and cites the
  source that requires it;
- LIVE gates and helper verbs are byte-for-byte inherited from the parent or
  an explicit commander-approved live contract; and
- no new leaf has the same normalized goal, files, gate and done-when as the
  target or any ancestor.

Every generated CODE gate is stored with `gate_reviewed_first: true`; the drive
loop's existing review and gate box remain its authority boundary.

An invalid answer is recorded and gets the validator's findings through the
existing two-round planner repair rule. Each answered slicer failure spends one
of the target's own `slices`; at 3 the card is held and the loop alerts; a
hand-back (the hold removed, by any writer) resets the count; an outage spends
none. The loop never publishes a malformed
queue. This limit applies to invalid answers, not to recursive slice depth.

### 7. Progress and completion

A valid re-slice MUST remove the recorded blocker. It may be a molecule of one
only when that one contract is strictly narrower or adds the missing
prerequisite; otherwise it must divide the work. A new ID does not reset a
failed contract: an ancestor signature match is refused.

There is no slice-depth limit. Each valid child has its own atomic build and
review rounds. The campaign continues with other startable leaves while one
lineage waits.

Publishing is successful only when the complete new molecule is visible and
the old leaf is `sliced`. On restart, the slicer MUST finish or roll forward a
published child whose parent status was not yet changed; it MUST NOT create a
duplicate.

The slicer is complete when these behaviours are proved:

1. one approved uncovered claim creates one whole, readable molecule;
2. stages create only the declared order and parallel atoms remain parallel;
3. a leaf can be re-sliced repeatedly, with stable ancestor IDs, and downstream
   work starts only after its deepest leaves settle;
4. invalid, duplicate, path-escaping and authority-widening answers change no
   backlog file;
5. a crash between child publish and parent update is recovered without a
   duplicate; and
6. `NO_GAP` cannot close source slicing without an independent accepted review.

## Driver impediments — record, do not fix under the freeze

1. The unchanged driver has no hook that invokes a slicer after
   `needs_slice`, spent rebuild rounds or spent replans. A standalone slicer can
   prepare and repair its backlog between driver runs, but automatic recovery
   needs one later call at the top of a turn.
2. `Backlog.slice_task` cannot add a row to a tree backlog because the tree has
   no file path for that row. The standalone slicer must publish a whole folder
   itself; later integration needs a public tree-publish door.
3. Campaign state records a backlog and goal, but not approved source paths or a
   reviewed source digest. The standalone command must receive and record them
   beside its own output until the campaign contract can carry them.
4. The existing contract replan has no tools, while the slicer is required to
   read specs and code. The standalone slicer can still take its intelligence
   from `resources.belt("plan")` and give that resource only Read, Grep and Glob;
   later integration needs that read-only call shape.
5. These are integration limits, not reasons to weaken the slicer's validation
   or edit the running driver.


## Evaluation: the spec against its first hand-run (2026-08-31, WATCHER)

Three walls stood tonight — T25 (gate failed the same way twice, then
quarantine), T4.close (rebuild rounds spent), T26.facts-spec (rebuild rounds
spent). I sliced them by hand, then judged each action against this
specification. Verdict per card:

- **T4.close — the spec's harness-fault rule fired correctly.** Its three
  rounds died on a combined-gate failure whose reason the keeper discarded — a
  harness fault, and §3 says a harness fault MUST NOT be sliced. The right
  action was fixing the harness (CombinedGateFailed now carries the failing
  gate's last words) and requeuing the card untouched. The spec was right and
  would have prevented a wasted slice.
- **T25 — a wall, but the evidence was silence.** The gate failed "the same
  way" twice, and the way was an empty string: its run leg piped everything
  into `grep -q`. The spec's wall predicate counts repeated gate failure as
  task-shape evidence, but SILENCE is not a signature — two empty outputs
  prove only that the gate cannot speak. Slice applied: the gate now prints
  before grading; no child molecule was owed.
- **T26.facts-spec — a true task-shape wall, sliced in place.** Round 3 died
  for restating story-schema canon; the contract now says cite, never restate,
  with the ownership boundary named. Under this spec it should have been a
  child molecule with `sliced_from`; in the still-flat backlog the equivalent
  was an in-place contract rewrite under the single-writer lock, which holds
  the spec's crash-safety property (one atomic write) by different means.

What the run teaches the spec — three amendments owed before approval:

1. **Rounds burned by a harness fault need an owner.** §3 rightly refuses to
   slice them, but nothing in the spec says who resets the spent rounds once
   the harness is fixed. Tonight a person did. Give the slicer (or the doctor)
   the authority: on a recorded harness-fault fix, rounds spent against it
   reset with a written why.
2. **The wall predicate must refuse silence as evidence.** "Failed the same
   way N times" where the way is empty output is a gate defect, not
   task-shape; the shared predicate should route empty-output repeats to
   gate-repair, never to re-slice.
3. **Name the interim.** The spec presumes the tree cutover; until
   `where.backlog()` names a folder, the flat-backlog equivalents are: child
   molecule → successor card with `sliced_from`; atomic folder publish →
   one `set_status` write under the writer lock. Both preserve the properties
   the spec wants; say so, or the first implementer will invent their own.

Net: the specification survived contact — it correctly forbade one slice,
correctly demanded one, and its crash-safety intent held in the flat backlog.
The three amendments are gaps it could not have seen without a live wall.
