# Brief — the loop resolves its own stalls

Status: brief for a campaign. Behaviours, not code. One class per section; each names the
evidence that paid for it, what the loop does instead, and the seam it plugs into.

## Why

A campaign of 119 cards ran four times in one day. It never stopped for want of work: it stopped
because cards ended in a state only a person could clear. A person cleared 40-odd of them by
hand. None needed judgment a machine lacks; each was one of nine repeatable classes. The loop
already classifies an ending (`triage_signatures`, the Jev rung in `triage_jev`, the text belt) —
but for these classes the route ends at `needs_a_person`. This brief moves the repair into the
loop. A person is paged only when a bounded repair has been tried once and the state repeats.

## The rule every class obeys

One incident, one decision, one repair, then the original gate again. Deterministic signatures
first; an unmatched ending goes to the decisions model once (`decisions.ask`, gate 0.6); a
below-gate answer gets one paid text diagnosis; then stop with the evidence. Every attempt is
written to the campaign's event log before it is made, so a crash cannot spend it twice and a
restart cannot reset it. No repair rewrites a gate to prove less, widens a card's files, or
starts another repair. A repeated fingerprint stops the episode.

## Classes

### 1. A provider's limit is never a card's verdict

*Evidence.* Two cards ended `rejected`: "the builder's call went wrong (limit) 3 rounds running;
a person re-slices". The account had hit its session limit; nothing was wrong with either card.

*Behaviour.* An ending whose cause is the provider — quota, session limit, rate limit, auth
expiry, network — charges no round to the card. The card returns to `todo` with its rebuild
state intact. One cooldown is shared by every card on that account, recorded in the campaign so
a restart keeps it. While an account cools down the loop uses the next configured provider
(policy: Claude first; on resource failure only, Codex `gpt-6-astra`, effort high); a code or
test failure is never treated as unavailability. When every provider is cooling, the driver
waits out the shortest cooldown instead of burning rounds.

*Seam.* `triage_signatures` (a `resource` signature ahead of the rest), the round accounting in
`loop_judge_retry`, provider choice in `providers`.

### 2. A finished card is never re-opened

*Evidence.* Five cards. Two kept judges (`kept_at` set, commit on the campaign branch) were
sent back when the code they judged landed: their red-first gates turned "green too early", the
combined gate blamed them, and they ended `blocked_by_agent`. Three code cards ended
`green_already` because another card had delivered their work.

*Behaviour.* A card whose kept commit is an ancestor of the campaign branch is `done`, and
nothing but a person changes that. A red-first gate belongs to the moment before its code
exists: once the code it waits for is kept, the judge's obligation inverts — the same test
must now PASS — and that is the gate the combined check runs for it from then on. Leaving the
judge out instead would drop the regression check the judge exists to give. A card found green before any work, whose files no open card owns, ends
`dropped` with a line naming the card that delivered it — not `green_already` for a person.

*Seam.* `loop_judge_gates._gates_on_the_branch` and `_send_to_its_owner`; the red-first step in
`loop_evidence`.

### 3. A sliced parent settles on the cards that name it

*Evidence.* Twelve parents were cut by hand into pieces in their own folders, each piece naming
its parent in `sliced_from`. `settled()` reads a parent's pieces from the parent's `Needs` only.
Seven parents could never settle and everything behind them waited for ever; three with old
needs settled at once and released their dependents early.

*Behaviour.* A `sliced` card is settled when every card naming it in `sliced_from` is settled,
as well as everything in its `Needs`. `doctor` reports a `sliced` card that no card names and
whose `Needs` is empty, because it can never settle.

*Seam.* `backlog_status.settled`, `doctor`.

### 4. A replan may remove a claim, never add one

*Evidence.* Seven refusals across four cards. The contract reviewer refuses a card whose Goal,
Done-when or Note claims more than its gate proves. The replanner answered by writing more
structure into the Goal ("one @Transaction in SetDao…") and freezing it, so each round the card
proved less of a larger claim.

*Behaviour.* A replan of a refused contract may strengthen the gate, or move a sentence from
Goal, Done-when or Note into Why (context the reviewer does not hold the gate to). It may not
add a claim. For a code card whose judge was written and reviewed separately, the contract is
"the gate passes". For a stub, the template is a compile probe the gate itself carries and
removes; the builder owns only the product file.

*Seam.* `replan`, `replan_prompt`, the slicer's card templates.

### 5. The builder is told which tools it holds

*Evidence.* Two builders ended BLOCKED: "write permission was not granted". The card lacked
`may_add_files`, so the builder held `Edit` and not `Write`; it tried `Write` on an existing
file, was denied, and stopped.

*Behaviour.* The build prompt states the tools granted for this card in one sentence ("you may
Edit the listed files; you may not create files"). An ending that says a listed file could not
be written is a harness fault, not a card's: the round is refunded and the card requeued once
with that sentence.

*Seam.* `prompts`, `tools.builder_tools`, `triage_signatures`.

### 6. A ref moved by someone else is not the gate's doing

*Evidence.* A person committed to the repository's `main` while a keep was being checked. The
keep gate fingerprints protected refs; it read the move as "a gate changed the candidate tree",
refused a finished suite's keep, and named an innocent card's gate as the one to repair.

*Behaviour.* When the fingerprint changes, the refusal's first line names what changed. If only
a protected ref moved and the checkout's tree is unchanged, the keep check is run once more from
the start; the gate is blamed only if the ref moves again under the same gate.

*Seam.* `keep_gate`.

### 7. A rebuild round re-reads the world

*Evidence.* A placement card was sent back because an older card's gate failed beside it. The
older gate was then corrected. Three further rounds replayed the recorded failure to the builder,
who answered each time that the old gate needed retiring.

*Behaviour.* A recorded rejection that quotes another card's gate is kept only while that gate's
text still exists in the backlog. Before a rebuild round, the combined gate list is derived
again; a rejection whose gate is gone is dropped and the combined gate re-run before any builder
is called.

*Seam.* `loop_judge`, `prompts` (the rebuild prompt), the card's `rejections`.

### 8. A recorded gap is checked again before the driver stands down

*Evidence.* Three runs ended rc=78 "the plan phase has not closed the source gap" after cards
covering the gap had been built and kept.

*Behaviour.* Before standing down on a recorded gap, the driver asks whether the claim the gap
names is now covered by a settled card; a covered gap is closed with the card's id, and the run
ends 0.

*Seam.* the gap record (`source-gap-ended.json`), the driver's ending in `graph-goal`.

### 9. A kept gate that asserts absence is a finding

*Evidence.* A stub's probe asserted that a function still threw `NotImplementedError`. It was
kept; the card that then wrote the function could never be kept beside it.

*Behaviour.* `doctor` reports a `done` card whose gate text asserts that something is missing
(`NotImplementedError`, `TODO(`, "must fail", "green too early") and whose files an open card
also lists. The stub template in class 4 never asserts absence.

*Seam.* `doctor`.

## Not in this brief

The decisions model's own availability (its key, its cooldown) follows class 1. A recursive
supervisor, a gate that is weakened to pass, a counter that a restart resets — none of these is
a repair; each hides a stall.

## How it is built

Cards are written by one planner pass, each with a gate that carries its own probe over a
temporary backlog, proved red on today's tree and green against a candidate before it lands —
the pattern that closed the cut check's seven fix cards without a refusal. The slicer's cut
check judges the cards once the decisions key is present. Order: 1, 2, 3 first — they are what
ends an unattended run.
