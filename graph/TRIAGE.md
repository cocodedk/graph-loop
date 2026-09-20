# TRIAGE — implemented plan and specification (2026-09-01)

TRIAGE names why a graph-loop run ended badly and sends that cause to the
right next actor. It is a sibling of the slicer. It does not build, slice,
keep, drop or supervise work.

Status: implemented on `codex/triage-loop`. The turn opener now calls
`lib/triage.py:triage_pending` after `graph-goal.py` reconciles and pushes pending
keeps, and before it reads flags or runs replan and slicer. Integration is
complete.

## Plan

1. Read every closed campaign boundary that has no verified TRIAGE cursor.
2. Classify from recorded evidence, using deterministic signatures first.
3. Persist the decision before any effect, then write the card once and route
   only the small consequence.
4. On the first historical pass, preview every sweep, alert and proposal. Apply
   nothing until a decision approves that exact preview (a person until
   2026-09-08; the decider until 2026-09-18, when it was cut — nothing writes
   that approval now, so a standing preview says so once and waits).
5. On later passes, process new endings once. A task's first `unknown` may use
   one read-only call from the existing plan belt; there is no model loop.

## Review of the plan

The simplest-design check stops at existing parts wherever possible: the
append-only campaign log is the queue and cursor, the backlog is the card store,
the plan belt supplies the one bounded judgment call, the board carries alerts,
and the existing gate-review marker guards repaired gates.

- A second daemon is unnecessary. One idempotent turn-top function covers lane
  endings, later quarantines and crash recovery.
- `run_lanes` does not return useful outcomes. Reading the durable log is both
  simpler and able to catch up old campaigns.
- Historical actions must not run unseen. One named preview marker is smaller
  and safer than a new approval service.
- A depth limit, retry queue or new task type would recreate the wall. TRIAGE
  only names and routes causes; the slicer owns smaller work.
- Generic whole-tree writes are unsafe on the current legacy tree. TRIAGE
  patches only the owning card's top-level `triage:` line and preserves every
  other byte and the file mode.

Review result: one function, one cursor kind, one preview kind and the existing
actors are enough. No new process, database, queue or driver rule is needed.

## Specification

### 1. Entry point and scope

`triage_pending(book, space, call=None)` MUST be called once at the top of a
normal driver turn, before replan and slicer read card verdicts. It MUST be safe
to call again after success or after a crash at any recorded step.

TRIAGE MUST NOT:

- run in `watch.sh` or `supervisor.sh`;
- change the driver, picker, doctor, builder, keeper or slicer;
- build, slice, keep, drop or commit task work;
- edit a LIVE gate, meaning a card with `gate_has_side_effects: true` or no
  `files`; or
- decide that finished work is live again.

### 2. Durable boundaries and cursor

A claim closes at its `released` event. If release is missing, the next
`claimed` event for the same task closes the old boundary. A `quarantined`
event outside a lane is its own boundary. A claim with no closer remains open.

An empty boundary has no outcome to classify, but TRIAGE still advances past it
without clearing or replacing the standing card verdict.

The full ordered result of `space.events()` is the record. A cursor event has
kind `triage` and records:

- `task`;
- `closed_index`, the closing event's zero-based position in that full record;
- `closed_at`, human provenance only;
- `closed_kind`;
- `verdict`, one verdict or null; and
- `card`, either the written verdict, `cleared`, or `unchanged`.

The full-log index alone orders boundaries. Before trusting a cursor, the
reader MUST verify the indexed event's task, time and kind. A stale cursor
selects every boundary whose time is equal to or later than the recorded time,
then processes them in full-log index order. Equal seconds are included, so a
duplicate is possible but a lost boundary is not.

### 3. Decision and write order

For every pending boundary, the durable order is:

1. `triage_model` before any model call, when one is allowed;
2. one closed-shape `triage_decision` for that exact boundary;
3. its card, sweep, alert or proposal effect; and
4. one `triage` cursor.

On recovery, a valid stored decision is reused. A malformed or partial decision
is ignored. An answered call is never bought again, even if the process died
before saving its answer; that card is then the plan phase's
(`lib/plan_phase.py`).

Cards are written once per open task, using its latest actionable boundary.
An `accepted` ending is the only ending that may clear the standing `triage`
field, and does so only if the card is still open. An empty boundary does not
clear. `done` and `dropped` cards are classified in the record but never edited.

### 4. Verdicts

Every outcome that did not keep work receives exactly one cause:

- `work`: the work or its size is wrong;
- `contract`: the card or its proof is wrong;
- `gate`: the check is mute or wrong;
- `rig`: test support names work outside the card;
- `environment`: the interpreter, helper or runtime did not run;
- `harness`: the loop, provider or campaign machinery failed; or
- `unknown`: the evidence cannot support another cause.

An accepted ending has `verdict: null`. A `needs_a_person` ending stays
`unknown` with signature `person-queued` and does not call a model.

Signature order is behavior. Mechanical explanations win before task-shape
ones: environment, rig, gate, then speaking repeated work. Provider and
campaign faults remain harness causes. A missing path is environment only when
it lies outside the card's own files. Silence is gate evidence, never work
evidence.

Each deterministic signature row MUST name the incident that paid for it.
`unknown` is an honest result, not permission to guess.

### 5. The one intelligence call

Only a task's first unknown may call the model, and never during the historical
catch-up. A historical unknown counts: a later unknown on that task is its
second, and the card is the plan phase's from then on. The call:

- uses `resources.belt("plan")` at medium effort;
- is read-only and has no tools;
- receives bounded, untrusted evidence;
- returns one closed JSON object with only `verdict` and `why`; and
- leaves the normal artifact, step and attempt records.

Amended 2026-09-19: Jev answers first. `lib/triage_jev.py` sends the same evidence
to OpenRouter's decisions endpoint (`lib/provider_jev.py`) as one choice question
over the seven causes, and its answer is the verdict when it names one of the six
that are a cause. `unknown` is asked, so that both models answer the same question,
but it is never acted on: it means there is not enough evidence, which is the
absence of a cause, and taking it would spend the card's one chance on a shrug and
raise "unknown twice" a round early. Everything else returns nothing too — no key,
no answer, an answer carrying a field this loop does not know, an `error` beside an
answer, a cost that is not a number — and the belt call above then runs exactly as
before.

The rung sits in FRONT of the belt rather than on it: the belt stops at the first
resource that answers, so an unreadable answer on it would have ended every unknown
as unknown. Nothing in the call may raise, because the `triage_model` marker above
is written before it: a fault would kill the driver turn AND cost the card the text
answer it is owed. With no key there is no call and no record. Otherwise Jev leaves
its own step, question, answer and attempt records, filed under the `plan` account
like every other planning and triage call. A caller that passes its own `call` gets
no Jev.

The `triage_model` marker is written first. A second unknown, a prior marker, a
bad answer or an unavailable belt leaves the card to the plan phase without
another model chance here. The first historical catch-up makes zero model calls.

Amended 2026-09-08 under the owner's order that the loop never waits for a person to
read or evaluate text (CLAUDE.md § Code). The catch-up itself is unchanged: it
still makes zero model calls, and the preview it writes is decided afterwards,
never inside the catch-up.

### 6. Repairs and queue sweep

TRIAGE may apply only repairs in the deterministic repair table, and only when
the function changes the gate. Membership in the table alone proves nothing.

A deterministic signature present in the repair table starts one scan. A card
confirms the repair only when the function changes that card's current gate.
The scan covers all open cards once and emits one `triage_sweep`
event naming changed and LIVE matches. A changed CODE gate receives
`gate_reviewed_first: true`, and a card the loop had parked on that gate goes
back to `todo` for its builder IN THE SAME WRITE as the gate — the two apart
left a death between them with the gate repaired, the card still parked and its
refund lost — — never a card a person holds, a sliced parent,
or a card the slicer already owns: a repair gives an owner to a card that had
none and never changes who owns one. A LIVE match is not edited and alerts a
person only when the sweep is live.

Every sweep carries its source boundary. An approved historical sweep also
carries the exact preview index and exact task scope. These identities prevent
a crash from repeating a sweep and prevent a later same-signature sweep from
standing in for the one a person reviewed.

### 7. First catch-up and approval

The first catch-up MUST:

- process every historical boundary in full-log order;
- write at most one verdict per open task;
- make zero model calls;
- apply no repair and fire no route;
- emit dry `triage_sweep` events; and
- emit one `triage_preview` after all boundary cursors, even when its
  `would_alert` and `would_propose` arrays are empty.

Activation requires a file named `triage-approved` in the campaign folder. It
HOLDS the effects that were approved — the preview's full-log index, each
sweep's signature, scope, exact gate changes and LIVE matches, and the routes —
together with the request that approved them. An approval for another preview
approves nothing.

Activation reads it under the backlog lock and applies what it holds, never a
recomputation: its own first sweep changes the gates a recomputation would read.
The approval keeps, for each repair, what it will FIND — for every card in its
scope, the gate it will read, whether that card is LIVE and whether it is still
open — as well as what it would write. They are previewed in the order they RUN,
each against what the ones before it leave, so two on one card do not both
expect the same gate.

ONE rule then decides whether a repair may run: apply it only if the card is
exactly what the approval says it will find, in every field the repair reads.
Anything else is a card nobody reviewed, and the activation stops there — an
approval that says nothing about the cards, one written before this was
recorded included, applies to nothing and is decided again. A repair that has
already run is not asked that question: its own sweep record, or, when a death
lost that record, the cards already holding the gate it would write — an edited gate stops the activation instead
of being repaired unreviewed, while cards that already hold the exact gate the
approval names are this loop's own work, not an edit. A missing approval raises
one visible waiting alert.

Amended 2026-09-08 under the same order: the marker is written by the loop, not
by a person. A preview with effects needs an approval of its own; its input is
the exact index, the proposed routes AND
the dry sweeps those arrays say nothing about, read once by
`triage_preview.effects_of` so what is approved is what happens — including the
exact gate each repair would write, asked through the rule the sweep walks
(`triage_repairs.would_change`), so a gate edited after approval makes the
answer stale. A preview that would change no open card and route nothing is
consumed with no decision at all. An approval
writes that record and calls this same activation, and whichever turn performs
the activation stamps `triage_activation` with the request it names — so a
decision can prove its own effect ran rather than reading a subject that went
quiet as one that was applied. A refusal's receipt is read the same way: it is
on the platter before the event that announces it, so a death between the two
does not discard a decision that ran.
Inputs that changed under the answer invalidate it, and another preview needs
another decision. A refusal is a durable receipt under `<campaign>/previews/`
that the activation READS, so the preview stops waiting; the cards it named keep
whatever actor they already have. A preview that would sweep nothing and route
nothing is consumed mechanically, with no decision and no model call. Finished
cards and LIVE gates are protected exactly as before.

A matching marker applies only that preview's stored task scopes, fires only
its stored routes for cards still open, and writes one `triage_activation`.
Every effect is idempotent across a crash. Approval of one preview never
approves another.

### 8. Routes

Only each task's latest pending decision may route:

- repairable `gate`, `rig` or `environment` causes use the mechanical repair;
- non-repairable mechanical causes leave the card to the plan phase: the alert
  is still raised, because it is how a person SEES what happened, but it is a
  message and never a handoff (CLAUDE.md § Code);
- `harness` emits a loop-brick proposal and keeps any existing worktree;
- `unknown` alerts after its second distinct boundary or after its one model
  chance is spent, and the card is the plan phase's from then on;
- `work` is read by the existing slicer wall rule; and
- `contract` is read by the existing replan/slicer contract path where that
  path applies.

Finished cards receive no delayed alert, proposal or repair. Partial route
emission is replayed without duplicates.

## Proof on the real campaign copy

The implementation ran against a copy of the current campaign and tree, never
the live campaign:

- 572 boundaries processed: 383 outcomes and 189 empty boundaries;
- verdicts: contract 202, environment 6, gate 5, harness 17, work 88,
  unknown 40, and 214 null;
- 15 open cards changed and the same 15 cursor events named a card action;
- zero done or dropped cards changed and zero model calls;
- quarantine split: 14 harness, 1 gate and 2 environment;
- the other three harness endings were T7.s13-route at full-log indices 4436
  and 4463 (`resource-unavailable`) and T4.signin at 4811 (`provider-fault`);
- dry previews named 4 mute-gate cards and 6 scrubbed-Python cards;
- the watchdog wrong-task proposal carried all three matching boundaries; and
- exact approval applied two sweeps and one proposal once; a repeat changed
  nothing.

The focused suite contains 54 asserted tests. It covers stale cursors, tree
links and exact bytes, CRLF and file modes, model-marker crashes, exact preview
scope, delayed finished cards, and partial replay. the linter is clean and
every code and test file is below 200 lines.

The full graph suite ran 636 tests in this worktree: 635 passed. The one stable
failure is the hardcoded-path driver defect recorded below, outside TRIAGE.

## Impediments — integration ledger

1. **Done:** `graph-goal.py` — the reconcile and push-if-behind boundary the call
   sits behind; the call itself is in `lib/turn.py:turn_opens`.
2. **Done:** `lib/turn.py:turn_opens` — the triage call before `replan_pending`.
3. **Done:** `lib/backlog_status.py:is_wall` — the contract now requires a
   recorded verdict.
4. **Done:** `lib/triage_intelligence.py` records triage's paid calls on the plan
   account, which `lib/doctor_spend.py` exempts from costly-silence findings.
   `purpose="triage"` is recorded but read nowhere.
5. **Done:** `lib/backlog.py:Backlog._apply` — setting a card to done clears its
   standing verdict.
6. **Done:** `lib/workspace.py:Workspace.event` — one shared guard stamps `turn=`
   on every event from the space-level turn context. Triage does not depend on it.

Status: built, accepted and integrated; both blocking review findings are fixed.
The turn-top call site, turn opener, wall contract, paid-call exemption and keep
cleanup are wired, and lane events carry their turn provenance.
The accepting review's other three findings are non-blocking follow-ups.
