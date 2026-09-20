# The loop's diary — what we learned building and running it

Every entry is a thing that happened, what it cost, and the rule it produced. The
rules live in `CLAUDE.md`; this file keeps the story behind them, because the
next person to build a loop will not believe the rules without it.

Written as we go. Newest last.

## 2026-08-28 — the day the loop was built and first run

**What it is.** `drive-goal.py` works a backlog of atomic tasks to done: it picks
the next task whose dependencies are met, proves its gate red, has the contract
reviewed by Codex before anything is edited, gives it to a Claude builder in its
own worktree, runs the gate, has the diff reviewed, and commits accepted work to
a campaign branch. It stops for nothing except a stop flag, a human hold, and its
own watchdog.

**Built test-first in six hours**, module by module: the backlog picker, the
provider calls, the gate runner, the campaign's record, the worktree and its
locks, the task loop, the report, the watchdog, the keeper, the planner. 131
tests, every file under 200 lines.

### The pilot, on a throwaway file

Four runs on a two-line Python file, before anything touched the real repository:

| run | outcome | wall | cost | what it taught |
|---|---|---|---|---|
| 1 | refused | 8s | $0 | the reviewer refused a gate a hard-coded answer would pass |
| 2 | refused | 33s | $0 | it refused the fix too: two fixed names is still hard-codeable |
| 3 | failed | 30s | $0.19 | the work was right; the loop called `__pycache__` an illegal edit |
| 4 | done | 105s | $0.19 | gate green, review accepted, backlog marked done |

The three cheap refusals are the point: no builder was called until the contract
survived review, so a bad task cost seconds and nothing.

### The first real campaign

Nine tasks, **zero builds**, $0.00, and 99.5% of the clock in review. Every task
was refused at the contract step, and every refusal was fair:

- gates that searched for a word instead of running a test (a comment containing
  `verdict_reasons` would have passed);
- a goal naming a file the task was not allowed to edit;
- one task that was thirty-eight tasks;
- a gate that was already green, proving nothing;
- pipelines that swallowed the exit code they were judging.

A backlog written for a person to read is not a backlog a loop can run.

### Six defects the run found in the loop itself

1. **The spin.** A refused task stayed `todo`, so the picker handed it back every
   few minutes and paid for the same review each time. Now every ending writes a
   status the picker will not re-offer.
2. **The banner.** A reviewer killed mid-call had its startup banner parsed as its
   verdict; three good tasks were quarantined for a rejection nobody wrote. A
   review that did not happen is now a harness fault.
3. **The denials.** A builder was refused three `cd &&` shell commands, worked
   around them, and finished the task correctly in thirty turns — and the loop
   threw the work away because denials were classified as failure. Denials the
   builder worked around are notes now.
4. **The wrong tree.** Gates written with absolute paths ran in the main checkout
   instead of the task's worktree, so they judged code the builder never touched.
   Every gate is relative now, and the rule is written into the backlog file.
5. **The stale count.** The watchdog counted turns since the campaign began, so
   eleven old refusals condemned a task whose builder had just succeeded. It
   counts since the last sign of progress.
6. **Nothing was kept.** Accepted work lived in a temporary worktree: a reboot
   would have erased the weekend, and the next task would have started from a
   HEAD that predated its own dependency. Accepted work is committed to
   `campaign/drive`, and each task starts from that tip.

### The first accepted task

`T11.principals` — the roster spec's principal table disagreed with the seed. The
builder found the spec was wrong (it was missing four principals the seed already
held), added exactly those rows, and left the seed untouched. Gate green, Codex
accepted, and kept.

It took five minutes of builder time and $2.73, and it was nearly lost three
times: once to the denials, once to the stale turn count, once to the absolute
path in its gate. Every one of those is now a test.

### What the numbers said

Reviews are the bottleneck, not the work: on the pilot, 88% of the clock; on the
first campaign, 99.5%. That is the price of refusing early, and it is worth it —
but it means the way to make the loop faster is better task contracts, not faster
builders.

## The tools, and why each exists

**`drive-goal.py`** is the driver. Six verbs, and the one that matters most is
`approve`: a campaign that has been initialised does nothing at all until someone
approves it, so a half-written backlog cannot start spending on its own.

**`supervisor.sh`** is the supervisor. It exists because the driver is a process and
processes die: it restarts one that exits, writes a report snapshot after every driver exit, and
— after the first version restarted a broken driver 1,440 times in a day would
have — backs off and gives up after five immediate failures.

**`watch.sh`** is the window, and it earned its place three times in one evening:

- it showed `work 0s   judging 1065s`, which is how we learned the reviews were
  the bottleneck and the builders were never being called;
- it showed a task `quarantined` seconds after its contract had been accepted,
  which is how we found the watchdog counting turns since the campaign began;
- it showed a refusal without a timestamp, which had us fixing a problem that was
  already fixed an hour earlier — so now every line it repeats carries its time.

It reads everything from the campaign's own log rather than from anything held in
memory, so it tells the same truth after a restart, and it says the alarming
things in words ("SUPERVISOR IS NOT RUNNING") rather than leaving them to be
inferred from a process list.

**`sc`** is the same idea for the live stack: the eight moves we were retyping
twenty times a day, behind one verb each.

The rule underneath all four: **a loop you cannot watch is a loop you will kill by
mistake** — and the first thing anyone does to a loop they cannot read is kill it.

## The queue behind one task

The owner looked at the backlog and said it worried him without being able to say
why. The number that explained it: **23 tasks to do, 3 startable.** Twenty of
them hung off one chain — T1 (the broker naming its refusing dependency) → T2
(a dev run closing) → T3 (a production run closing) — because when I wrote them
I gave each task the dependency that felt true rather than the one that was.

Freeing a stuck production run does not need the broker to name its dependency;
it is a replan. Mapping a fact onto the board is proved against recorded
fixtures, not against a live run. Naming the red harness scenarios is reading a
test report. Cutting those three false edges took startable from 3 to 14.

The rule: a backlog is measured by what can start now, not by what is written.


The finished design is written as `BLUEPRINT.md` beside this file — the owner,
2026-08-28: "this is the best loop I have ever made; make sure we have the
blueprint and it is documented."

## The claims that outlived their drivers

Three crashed drivers left claims behind, and the liveness check could not see
it: `os.killpg` answered for the supervisor's process group, which every driver
shares, so a dead driver's claim looked alive as long as the supervisor ran. The
claims quietly held files hostage — T6.approver's blocked both of its siblings.
Released by hand; the rule (a claim carries its claimant's own pid) is in
the rules, and the fix belongs in `workspace.claim` the next time it is opened.

## The $6.83 that was nearly thrown away twice

T1 — the broker naming the dependency that refused — was the campaign's biggest
build (30 minutes, $6.83, gate green with 254 tests) and it was rejected twice
for the same invisible reason: `git diff` hides untracked files, so the reviewer
was shown a change that imports a test it could not see, and refused it — twice,
correctly. The fix (intent-to-add before the diff) carries its own test now.

The salvage then took three more review rounds, each finding real: a comment
claiming a 502 the record never held, a suite count nobody asserted, a reasons
spec row the change had made stale, an overclaiming reason narrowed to the
stages the ledger proves, and the scheduler's fake broker brought along as a
co-change. Kept on the fifth look. The lesson is not that reviews
are slow — it is that every one of those findings would otherwise have been
found by a person, later, in production.

## 2026-08-28 evening — the $8.47 salvage that took seven rounds

T6.approver's build was rejected once by the loop's own diff review, then
salvaged by hand through the loop's steps: seven codex rounds, each finding a
real defect, each answered with a case proven red first — reference-following
broke on APPROVAL_VALIDATED; the first cycle's approver wore a later state; a
rejected latest cycle borrowed the earlier approver; a filed undecided cycle
did too; a truthy-but-incomplete evidence row disclosed a person past the
access rule; and twice the 200-line cap. ACCEPT on round seven, kept as
bb19c79. The reviewer was doing real security review of a trust boundary —
that is what max effort buys.

Mid-salvage, a `git stash` in the task worktree ate the fixed file (the stash
stack is repo-wide, the pop conflicted, a redirect truncated what was left).
The campaign's saved diff artifact under calls/T6.approver/ restored the
builder's work in one apply. The log is the product.

Same evening, the stack itself: every fast-mock identity token expired at
12:39Z (24h mint), and the rebuilt broker rightly refused them — runs died
authorize_call_failed http_401. Re-mint the tokens, recreate,
green again. Then NOT_VERIFIED found[] with no reason: the deployed broker
predated T1's verdict_reasons, so accepted campaign work was merged into the
run branch and the broker rebuilt — the journal will now name the refusing
dependency instead of an empty list.
