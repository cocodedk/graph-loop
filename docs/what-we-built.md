# graph-loop — what was built, and what it produced

A summary for a non-technical reader. Dates: **Saturday 29 August 2026** (foundations),
**Sunday 20 September** and **Monday 21 September 2026** (the work described here).

---

## In one paragraph

We built **graph-loop**: a system that takes a written specification and builds working
software from it, largely without a person at the keyboard. Over the weekend we then used it
on a real product — an Android exercise-logging app — as a live test. The app now works end to
end and passes **613 automated tests**. Just as importantly, the ways the system got *stuck*
were diagnosed and fixed, so the next project needs far less babysitting.

---

## What graph-loop is

Most AI coding tools are a conversation: a person asks, the AI answers, the person checks.
That does not scale past a few hours of work.

graph-loop is different. The work is written down as a **graph** before any code is written:

- A **node** is one capability a person would name — "the rest timer between sets".
- A **contract** is a promise one node makes to another, so they can be built independently.
- A **card** is one small work order: a goal, the exact files it may touch, and a **gate** —
  a command that proves the work is done.

The system then works the graph on its own: it slices nodes into cards, hands each card to an
AI builder, runs the gate, has a *second, different* AI review the result, and keeps the work
only if both pass. It runs several cards in parallel and stops for a person only when it
genuinely cannot proceed.

**The rule that makes it trustworthy: the test is written before the code, by a different
agent than the one that writes the code, and the test must be proven to FAIL first.** A test
that passes before the work exists proves nothing, and the system refuses it.

---

## What was achieved over the weekend and today

### 1. The system itself

| | |
|---|---|
| Code | ~16,400 lines across 149 modules |
| Its own tests | 301 test files, ~2,050 tests |
| Rule enforced on itself | every file under 200 lines; one third-party dependency |

Capabilities completed in this period:

- **Automatic parallelism** — the system measures the machine and decides how many builders to
  run at once, backing off when memory or test times degrade.
- **Memory and learning** — every node can carry notes and lessons learned, attached
  *alongside* the specification and never overwriting it.
- **A fast pre-check** — a cheap, sub-second decision model reviews every proposed slice of work
  *before* an expensive review is paid for, catching bad cuts early.
- **A self-diagnosing loop** — when a run stalls, it classifies why and repairs what it can.

### 2. A real product, built by it

An Android exercise-logging app: log sets by tapping once per repetition, see your tempo,
a rest timer between sets, a catalog of exercises you can extend, and a history screen with a
progress chart.

| | |
|---|---|
| Built from | 117 work cards across 12 capabilities |
| Result | 56 source files, ~2,900 lines |
| Proof | 107 test files, **613 tests, all passing** |
| Cost of machine time | ~$159 |

The app was installed on a real phone mid-build and the full journey was performed on the
device — choose an exercise, log a set by tapping, rest, log another, review history — with no
crash.

### 3. The honest part: what went wrong, and what we did about it

This is the most valuable result of the weekend.

On the first long unattended run, the system stopped constantly and a person had to rescue it
roughly **forty times**. None of those stalls were wrong *code* — the code it wrote was
correct. They were flaws in the system's own rules. For example:

- When an AI provider hit a usage limit, the system blamed the *work* and gave up on it.
- When a test card was correctly finished, the system later re-opened it and undid it.
- A finished piece of work could block everything behind it because of a bookkeeping gap.
- The reviewer refused correct work for hypothetical problems no honest builder would create.

We diagnosed each one, had a second AI propose the **smallest possible** fix for each, had a
third AI review those fixes independently — which caught two genuine defects that would have
let work be marked "done" without existing — and merged them only after all tests passed.

**Result:** the last stretch of the build ran with a fraction of the intervention. The specific
repairs a person was doing by hand are now the system's own job.

---

## Why this matters commercially

1. **Specification becomes the deliverable.** The written spec is not documentation that rots
   beside the code — it is the thing the system builds from, and it stays authoritative.
2. **Proof is built in, not bolted on.** Nothing is kept unless a test that was proven to fail
   now passes, and a second independent AI agrees. There is a written record of every decision.
3. **It runs unattended.** Work continues overnight. A person is needed for judgment —
   "does this look right?" — not for supervision.
4. **It improves itself.** Every stall this weekend became a permanent fix. The system is
   measurably better at the end of the project than at the start.
5. **Cost is visible and modest.** A working, fully tested application for roughly $159 of
   machine time over a weekend.

---

## Where it stands

- The system: **working and in use**, published at `github.com/cocodedk/graph-loop`.
- The app: **functionally complete and fully tested**, kept private for now, not yet released.
- Next: a visual design pass and seven further features, already specified as nodes and ready
  for the system to build.

## Honest limitations

- A person still writes the specification, and its quality decides everything downstream.
- A person still judges whether the result *looks* right; the system proves behaviour, not taste.
- It was proven on one real project. The fixes made this weekend are expected to hold, but the
  next campaign is what confirms it.
