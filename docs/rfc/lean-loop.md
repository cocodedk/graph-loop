# RFC: a lean loop — ship features, not proofs

Status: **proposal, 2026-09-23 — for the owner to decide.** Nothing here is built. If accepted, it is
carried out as the numbered steps at the end, one issue and one PR each, in that order.

## In plain words, with what actually happened

### How the loop works today, one step at a time

**1. A feature is cut into three cards.** "Show the overdue rest ring in amber" did not become one job.
It became a *stub* card (an empty function), a *judge* card (tests that must fail first, then are frozen),
and a *code* card (make the tests pass). The slicer's prompt asks for this split
(`slicer/asking.py:104`, `gate_until_kept`). Each card also gets its own hand-written shell script that
decides whether the card is done.

**2. Before anyone builds, a reviewer tries to prove the card wrong.** Its prompt
(`graph/lib/contract.py:72`, `contract_prompt`) asks: "what wrong implementation would still pass this
check?" If it can imagine one, it refuses the card. It can almost always imagine one.
*What happened:* N15's code card was refused four times in a row, each time for a new imagined hole in
tests that were already frozen and could not be changed (issue #72). N19's code card was refused and
rewritten about 95 times.

**3. A refused card is rewritten by another model, up to six times.** (`graph/lib/replan.py:111`,
`MAX_ROUNDS = 6` in `graph/lib/replan_budget.py:10`.) For most of the run, the rewriter could not even
read the code it was writing about, so it guessed names that did not exist (`SetRecord`, issues #70 and
#73). A small decision model (Jev) picks what to do with each refusal (`graph/lib/triage_path_jev.py:14`).
*What happened:* one day had 143 refusals, 98 rewrites and 45 cards kept. Rewriting cost $78, more than
building ($70).

**4. The card is built, then its own script runs.** These scripts grew into small programs. One N16
script was about 80 lines and built a deliberately wrong copy of the screen to prove its test would catch
it; it failed on its own machinery while the real test was fine (issue #97).

**5. Before a card is kept, every older card's check runs again** (`graph/lib/loop_judge_gates.py:22`).
*What happened:* N13's light status-bar test could not be added, because an older check insisted the same
test file hold *exactly two* tests. Adding a third, which is the whole point of the card, broke the older
check (fixed by hand in the profile, "a lasting gate filters to its own test methods").

**6. Kept work goes to a side branch, never to the app.** The keeper says so itself: "The main line is
never moved and never merged into; a person does that" (`graph/lib/keep.py:10`). Nobody was told to.
*What happened:* for 30 hours, 0 commits reached `main`. The app on the phone could not change.

**7. The design was never a job at all.** The plan called the look "a person's node: it is never a loop
card" (exercise-log `vault/N11-visual-design.md`, commit `f7b77e8`), so no card was cut for any screen's
look (fixed by #112 and #113).

**8. Busy counts as progress.** The watchdog counts "cards planned" and "a charged rebuild" as the
campaign moving (`graph/lib/watchdog.py:106`, `_is_progress`), so a loop that plans and rewrites all day
looks healthy.

### How it would work instead

1. **You say what you want, up front**, including how it looks (the design canvas), and answer anything
   only you can supply before work starts. The loop proves it can email you first (#114, `graph-goal.py
   contact`).
2. **One job per feature or screen, one builder.** "Restyle the Log screen to its artboard" is one job,
   not nine cards.
3. **The builder writes the feature and its tests together**, in its own copy of the code
   (`graph/lib/worktree.py` stays).
4. **The check is the same for every job:** the app builds and all its tests pass (the repository's own
   command, from `profile-android-gradle.md`). No per-job scripts.
5. **One other agent reads the change** (`graph/lib/loop_diff_review.py` stays). No pre-build hole hunt.
6. **If it fails, one more try with the error text. If it still fails, you get an email** saying which job
   and why (the channel from #114). No six rewrites, no model deciding what to do.
7. **Every run ends on `main` with an installable app, and an email to go look.**

*This is exactly how the screens were finished this morning:* Log (`cbe53e5`), running set and rest
(`3407921`), History and Catalog (`efe5b8d`), the remaining design details (`d3e21a6`), merged to
exercise-log `main` as `a217d37` and `a765737`. Five screens, about an hour, each gated only by "it
builds and the 744 existing tests still pass", then installed on the phone.

### What stays, what goes, in one line each

- **Stays:** separate copies of the code per builder (`worktree.py`), no access to passwords during checks
  (`gate_sandbox.py:11`, `MASKED`), every change committed, the event log and costs, the email channel
  (#114, #117), "no person inside a plan" (#112), the answer log (#95, #119), spending limits, the dashboard.
- **Goes:** the pre-build hole hunt (`contract.py`), the rewriter and Jev's path choices
  (`replan*.py` 336 lines, `triage*.py` 1,707 lines), three cards per feature and frozen tests, re-running
  every old check (`loop_judge_gates.py`), per-call model picking (`model_router.py:37`), automatic
  parallelism (`lanes*`, `throttle*`, `machine*`: 1,048 lines), and `remember`, doctor and report
  (2,379 lines).

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
