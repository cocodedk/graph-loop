# RFC: a lean loop — ship features, not proofs

Status: **proposal, 2026-09-23 — for the owner to decide.** Nothing here is built. If accepted, it is
carried out as the numbered steps at the end, one issue and one PR each, in that order.

## Why

On the exercise-log app, graph-loop ran for about three days. It kept about 250 cards, but after 30 hours
the app on the owner's phone had not changed: nothing had reached `main`, and no screen looked like the
approved design. Then, outside the loop, one agent per screen restyled all five screens in about an hour,
gated only by "it builds and the existing tests pass", and the owner judged the result on the phone.

What one day of the loop produced (campaign three, from its event log):

| | |
|---|---|
| Contract refusals / cards kept | 143 / 45 |
| Replans | 98 |
| Spend: replanning / building / planning | $78 / $70 / $116 (review not logged) |
| Test code / app code written | 1,790 / 618 lines |
| graph-loop issues filed / PRs merged | 57 / 40, most adding a rule |

Almost every refusal was about the proof, not the feature: Gradle's quiet flag, stale reports, failure
messages only in XML, lasting gates that forbade a class from growing, generated probe scripts, frozen
criteria, exit-trap parsing. Each fix added a rule, and each rule was a new way to be refused.

Three independent judgements agree on the size of the problem: Jev scores the machinery 60–80 % overkill
(confidence 0.86), Astra 60–70 % (about 13–15k of 21.5k lines), Claude about 65 %.

## The current flow

```
brief ─► plan phase ─────────────────────────────────────────────────────────────┐
         slicer/speccer cut specs into molecules of atoms;                        │
         each feature becomes three cards: stub → red-first judge → code;         │
         each card carries a hand-written shell gate                              │
                                                                                  ▼
run, per card:  claim → route (Jev picks model + effort)
                → CONTRACT REVIEW (reviewer hunts any wrong implementation the gate
                  would let through; refuses)                      ◄─────────────┐
                → triage (Jev picks: probe / accept / slice / rewrite / person)   │
                → REPLAN (a model rewrites the card; up to 6 rounds) ────────────┘
                → build in a worktree → run the card's gate in a sandbox
                → judge cards: prove red for the right reason, then freeze
                → diff review
                → KEEP CHECK (rerun every kept card's lasting gate on the combined
                  branch; blame an owner if one is red)
                → keep on the campaign branch
         lanes and a throttle decide parallelism; a watchdog and a doctor read the log;
         a parked card waits for the plan phase or a person
end: the campaign branch; merging to main and building an APK are left to a person
```

The loop's unit of work is a **proof**. A card is done when its gate, reviewed adversarially, passes;
a feature is done when its three cards are kept; the app is done when someone merges and builds it.

## The proposed flow

```
contact  ─► prove the channel to the person (already built, #114)
brief    ─► behaviour AND visual references, and the acceptance list; everything only a
            person can supply is asked here, before any card (already the rule, #112)
plan     ─► one card per feature or screen: goal, done-when, the files it likely touches,
            and only real dependencies. Tests are written with the feature, not as a card.
run, per card:  build in a worktree
                → gate: the project's own proof command (tests + build + lint, from the
                  repository's profile) — the same gate for every card
                → one diff review
                → merge into the integration branch → rerun the suite there
                → on a red suite or a refused review: ONE repair pass with the failure
                  text; still red → stop the card and email the person why
end of run: merge to main, build the APK, email the person that it is ready to accept
```

The loop's unit of work is a **shipped feature**. A card is done when the app still builds, every test
still passes, and one reviewer has read the diff. A run is done when the app is on `main` as an APK.

## Side by side

| Concern | Current | Proposed |
|---|---|---|
| Unit of work | a proof per atom (stub, judge, code) | a feature or a screen |
| What a card's gate is | a shell script written per card | the project's proof command, the same for every card |
| Tests | a separate red-first judge card, frozen once kept | written with the feature, in the same card |
| Before building | adversarial contract review, may refuse | none |
| After building | diff review, then the keep check replays every lasting gate | one diff review, then the whole suite on the integration branch |
| A refusal | triage (Jev) → replan up to 6 rounds → slice → person | one repair pass, then stop and email the person |
| Choosing models | Jev per call, or `GRAPH_ROUTER=off` | fixed: strong planner, fast builder, one reviewer |
| Parallelism | adaptive lanes, machine sensing, throttle | a fixed lane count; merging is serialized |
| Where work ends | the campaign branch | `main`, plus an installable APK |
| Visual design | outside the loop ("a person's node") | a card like any other; the person accepts at the end |
| Reaching the person | dashboard, ALERTS.txt | the proven email channel (#114) |

## What stays

Worktree isolation and the gate sandbox (credential masking); durable commits and preserved partial work;
the event log and cost records; the contact channel (#114) and "no person inside a plan" (#112, #113);
the answer command and its log (#95, #119); budgets and timeouts; the repository profile (the loop names
no build tool); one independent diff review; the dashboard.

## What goes (Astra's line counts at `0f2af2d`)

| Mechanism | Size | Replaced by |
|---|---|---|
| Adversarial contract review and its prompts | part of `contract.py`, `review_*` | nothing before the build; one diff review after |
| Staged stub → judge → code, red-first proof, frozen gates, `gate_when_kept` | `loop_evidence`, `loop_judge*`, `keep*` replay | tests inside the feature card; the suite as the gate |
| Per-card gate scripts and their scanners | four slicer modules, 634 lines | the profile's proof command |
| Replanner, triage paths, path questions | replan + triage: about 2.4k lines | one repair pass |
| Recursive slicing, source-gap campaigns | planning, slicing, source-gap: 4.1k lines across 36 files | one feature list, checked once against the brief |
| Jev routing per call | `model_router` and its evidence | fixed model choices |
| Adaptive lanes, machine sensing, throttle | 877 lines across 8 modules | a fixed lane count |
| `remember`, doctor, report families | about 2.4k lines | the event log and the dashboard |

## Risks and what guards against them

- **Less proof per card.** A wrong implementation can pass the suite. Guard: the diff review, the whole
  suite on every merge, and the person's acceptance at the end of each run, not at the end of a campaign.
- **A weak suite.** Where the suite is thin, the feature card itself adds the tests for what it builds,
  and the diff review checks they exist.
- **A card that keeps failing.** One repair pass, then it stops with its reason in the person's inbox.
  No card can spend more than two builds.
- **Losing what the proof machinery caught.** The regression tests it produced stay in the repository
  and keep running on every merge.

## Steps, one issue each

1. The gate is the repository's proof command from its profile; per-card gate scripts are no longer written.
2. Remove the adversarial contract review; keep the diff review.
3. Plan one card per feature or screen; stop cutting stub → judge → code; tests go in the feature card.
4. Replace triage, replan and re-slicing with one repair pass, then stop and email the person.
5. After each merge, run the whole suite on the integration branch; remove the lasting-gate replay.
6. End every run by merging to `main`, building the APK, and emailing the person.
7. Fixed model choices; remove per-call routing.
8. A fixed lane count; remove machine sensing and the throttle.
9. Remove `remember`, the doctor and the report families.

Each step is small on its own, deletes more than it adds, and leaves the loop working. If a step shows
the loop worse off, stop there.
