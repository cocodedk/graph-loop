# The loop's diary — what we learned building and running it

Every entry is a thing that happened, what it cost, and the rule it produced. `DESIGN.md`
beside this file is the finished design; this one keeps the story behind it, because the
next person to build a loop will not believe the rules without it.

Every incident here is real. None of them points at anything real: the work the loop was
built on was private, so the mechanism is kept and the names are gone. The numbers are
untouched — they are what makes a rule believable, and they identify nobody.

## Day one — built and first run

Built test-first in six hours, module by module: the backlog picker, the provider calls,
the gate runner, the campaign's record, the worktree and its locks, the task loop, the
report, the watchdog, the keeper, the planner.

### The pilot, on a throwaway file

Four runs on a two-line Python file, before anything touched a real repository:

| run | outcome | wall | cost | what it taught |
|---|---|---|---|---|
| 1 | refused | 8s | $0 | the reviewer refused a gate a hard-coded answer would pass |
| 2 | refused | 33s | $0 | it refused the fix too: two fixed names is still hard-codeable |
| 3 | failed | 30s | $0.19 | the work was right; the loop called a bytecode directory an illegal edit |
| 4 | done | 105s | $0.19 | gate green, review accepted, backlog marked done |

The three cheap refusals are the point: no builder was called until the contract survived
review, so a bad task cost seconds and nothing.

### The first real campaign

Nine tasks, **zero builds**, $0.00, and 99.5% of the clock in review. Every task was
refused at the contract step, and every refusal was fair:

- gates that searched for a word instead of running a test, so a comment containing that
  word would have passed;
- a goal naming a file the task was not allowed to edit;
- one task that was thirty-eight tasks;
- a gate that was already green, proving nothing;
- pipelines that swallowed the exit code they were judging.

A backlog written for a person to read is not a backlog a loop can run.

### Six defects the run found in the loop itself

1. **The spin.** A refused task stayed `todo`, so the picker handed it back every few
   minutes and paid for the same review each time. Now every ending writes a status the
   picker will not re-offer.
2. **The banner.** A reviewer killed mid-call had its startup banner parsed as its verdict;
   three good tasks were quarantined for a rejection nobody wrote. A review that did not
   happen is now a harness fault.
3. **The denials.** A builder was refused three shell commands, worked around them, and
   finished the task correctly in thirty turns — and the loop threw the work away because
   denials were classified as failure. Denials the builder worked around are notes now.
4. **The wrong tree.** Gates written with absolute paths ran in the main checkout instead
   of the task's worktree, so they judged code the builder never touched. Every gate is
   relative now, and the rule is written into the backlog file itself.
5. **The stale count.** The watchdog counted turns since the campaign began, so eleven old
   refusals condemned a task whose builder had just succeeded. It counts since the last
   sign of progress.
6. **Nothing was kept.** Accepted work lived in a temporary worktree: a reboot would have
   erased the weekend, and the next task would have started from a HEAD that predated its
   own dependency. Accepted work is committed to the campaign branch, and each task starts
   from that tip.

### The first accepted task

A specification whose table disagreed with the fixture it was generated from. The builder
found the specification wrong — it was missing four rows the fixture already held — added
exactly those rows, and left the fixture untouched. Gate green, review accepted, committed.

It took five minutes of builder time and $2.73, and it was nearly lost three times: once to
the denials, once to the stale turn count, once to the absolute path in its gate. Every one
of those is now a test.

### What the numbers said

Reviews are the bottleneck, not the work: 88% of the clock on the pilot, 99.5% on the first
campaign. That is the price of refusing early, and it is worth it — but it means the way to
make the loop faster is better task contracts, not faster builders.

## The tools, and why each exists

**The driver** has six verbs, and the one that matters most is `approve`: a campaign that
has been initialised does nothing at all until someone approves it, so a half-written
backlog cannot start spending on its own.

**The supervisor** exists because the driver is a process and processes die. It restarts
one that exits, writes an hourly report snapshot, and — after an early version would have
restarted a broken driver 1,440 times in a day — backs off and gives up after five
immediate failures.

**The window** earned its place three times in one evening:

- it showed `work 0s   judging 1065s`, which is how we learned the reviews were the
  bottleneck and the builders were never being called;
- it showed a task quarantined seconds after its contract had been accepted, which is how
  we found the watchdog counting turns since the campaign began;
- it showed a refusal without a timestamp, which had us fixing a problem that had been
  fixed an hour earlier — so now every line it repeats carries its time.

It reads everything from the campaign's own log rather than from anything held in memory,
so it tells the same truth after a restart, and it says the alarming things in words rather
than leaving them to be inferred from a process list.

The rule underneath all of them: **a loop you cannot watch is a loop you will kill by
mistake** — and the first thing anyone does to a loop they cannot read is kill it.

## The queue behind one task

The owner looked at the backlog and said it worried him without being able to say why. The
number that explained it: **23 tasks to do, 3 startable.** Twenty of them hung off one
chain, because when the tasks were written each was given the dependency that felt true
rather than the one that was.

Cutting three false edges took startable from 3 to 14.

The rule: a backlog is measured by what can start now, not by what is written.

## The claims that outlived their drivers

Three crashed drivers left claims behind, and the liveness check could not see it: the
check asked about a process group that every driver shares, so a dead driver's claim looked
alive as long as the supervisor ran. The claims quietly held files hostage — one blocked
both of its siblings. Released by hand. The rule is that a claim carries its claimant's own
process id, and it belongs in the claim function the next time it is opened.

## The $6.83 that was nearly thrown away twice

The campaign's biggest build — 30 minutes, $6.83, gate green with 254 tests — was rejected
twice for the same invisible reason: a diff hides untracked files, so the reviewer was
shown a change that imports a test it could not see, and refused it. Twice, correctly. The
fix — mark new files as intended-to-add before taking the diff — carries its own test now.

The salvage then took three more review rounds, each finding something real: a comment
claiming an error the record never held, a suite count nobody asserted, a specification row
the change had made stale, an overclaiming reason narrowed to what the record proves, and
an unrelated change brought along for the ride. Accepted on the fifth look.

The lesson is not that reviews are slow. It is that every one of those findings would
otherwise have been found by a person, later, in production.

## The $8.47 salvage that took seven rounds

One build was rejected by the loop's own diff review, then salvaged by hand through the
loop's steps: seven review rounds, each finding a real defect, each answered with a case
proven red first. A reference-following bug on one state; a first record wearing a later
state's approver; a rejected record borrowing an earlier one's; an undecided record doing
the same; a row that looked complete but disclosed a person past the access rule; and twice
a file over the size limit. Accepted on round seven.

The reviewer was doing real security review of a trust boundary. That is what maximum
effort buys.

Mid-salvage, a stash in the task's worktree ate the fixed file: the stash stack is
repository-wide, the pop conflicted, and a redirect truncated what was left. The campaign's
saved diff artifact restored the builder's work in one command.

**The log is the product.**

## The document that was wrong about its own code

The design shipped with a claim that the logic was generic and only four values were not.
Preparing to move the loop somewhere else, a reviewer checked the source instead of the
document. Four places named the work it was built for. The worst was not prose: the code
that creates a worktree copied four directories belonging to one project into every
worktree it made, with a comment citing the incident that caused it.

An inventory taken from the document missed it, because the search was spelled the way the
document spells things and the code spelled it differently.

Two rules, and they cost a full review round each:

- A document is not authority about the code it describes. A claim of genericness is a
  measurement, and the measurement is a grep of the source.
- Take the file list from the repository, not from the document. A hand-written list drifts
  from the tree it describes; `git ls-files` does not.

## The guard that contained what it forbade

The first version of the check that proves nothing private has leaked listed the forbidden
words inside itself — and then excluded itself from its own scan, because otherwise it
found them. It passed. It would have passed on a dirty tree too.

Split in two: a shipped half carrying only shapes that name nobody, and a private half
passed in by path that never enters the repository. The shipped half then failed on its own
pattern file, because a pattern that looks for a home directory contains one. Written so
the pattern text cannot match the pattern, it passes while scanning itself.

Then it was pointed at history rather than the working tree, and caught a leak that had
been committed and deleted — a clean tree over a dirty history.

The rule: **a new check is not trusted until the case it exists to catch has been made to
fail in front of you.** Every step above was found by trying to make it fail, and none of
them by reading it.
