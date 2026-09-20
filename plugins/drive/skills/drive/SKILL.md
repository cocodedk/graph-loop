---
name: drive
description: Use when breaking a large body of work into tasks an agent loop can run unattended — writing a backlog of atomic, gate-first task contracts, judging whether a task is ready to hand to a builder, or diagnosing a backlog that stalls. Also for reading a campaign log after an unattended run. Not for interactive work you intend to supervise.
---

# Slicing work an agent loop can run

This skill is the method. The driver that runs it is described in `docs/DESIGN.md`; the
method works without it, and it is the part that transfers.

The premise: **a backlog written for a person to read is not a backlog a loop can run.**
One campaign refused nine tasks in a row at zero cost, and every refusal was fair. The
backlog was the defect, not the models. Time spent here is the only lever on speed —
reviews are 70 to 99 percent of an unattended run's clock, so the way to make it faster is
better task contracts, not faster builders.

## First, decide whether to use a loop at all

Do not start a campaign when:

- **You cannot write the gate.** If you cannot name a command whose exit code says the work
  is done, you do not yet know what you want. Find out first, by hand.
- **The gate would pass today.** A gate that has never failed proves nothing. If it is
  already green, there is no task.
- **The work is one idea that takes a day.** A loop's unit is a task a builder finishes in
  about half an hour. Bigger than that and you are asking it to plan, which it will do
  badly.
- **You intend to watch it.** The loop's value is that nobody is there. If you are going to
  sit with it, work directly and save the review cost.
- **Judgement is the deliverable.** Design, naming, what-should-this-be — a gate cannot
  judge those, so the loop cannot either.

## Writing a task contract

A card is one note in a vault you can open in Obsidian. Front matter holds what the loop
decides; the body holds what a person wrote, and `Needs` is a `[[wikilink]]`, so the graph
view is the dependency graph.

````markdown
---
status: todo
files:                  # everything the gate can fail on, never the test that judges it
  - src/fetch.py
---

## Goal

one sentence, one idea

## Why

what it costs that this is not done

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

**Gates first.** Write the end state as commands that fail today. No task exists before its
gate does. Every path relative to the worktree, every stage in its own subshell, and the
exit code is the verdict — a pipeline that swallows the code it is judging is the most
common way a gate lies.

**One idea per task.** If describing it needs the word "and", it is two tasks.

**The file list is everything the gate can fail on** — counts, fixtures, pinned digests,
sibling copies — and never the test that judges the work. A builder who can edit the test
that grades it will edit the test. If writing that test *is* the deliverable, say so
explicitly in the contract, so the reviewer knows.

**Dependencies are only what is real.** A task waits for another only if it reads that
task's output. This is where backlogs die: give each task the dependency that *feels* true
and twenty tasks queue behind one. Measure the backlog by what can start now, not by what
is written. One backlog went from 3 startable to 14 by cutting three false edges.

**Mark the exceptional cases**: a gate that performs live actions rather than merely
observing, a task whose test is the deliverable, and anything a person must see before it
runs.

## Reviewing a backlog before it runs

Read each task and ask, in this order:

1. Does the gate fail today, for the reason the task exists?
2. Could the gate pass without the work being done? Searching for a word instead of running
   a test is the classic — a comment containing that word passes.
3. Does the goal name a file the task is not allowed to edit?
4. Is this one task or thirty-eight?
5. Does the file list include the test that judges it?
6. Are the dependencies real, or merely plausible?

Anything you cannot answer is a task the loop will refuse at your expense, but cheaply —
refusal happens before any building.

## When a task fails twice the same way

Two identical gate failures mean **the task is wrong, not the model too small**. Re-slice
it. Never raise the effort: a failed gate is a specification problem wearing a capability
problem's clothes.

## Reading a campaign

Everything is in the log, and the log is the product — it is committed and never thrown
away. When something looks wrong:

- **Where did the clock go?** By step and by task. If the builders are barely running, the
  contracts are the problem.
- **What can start now?** A long chain behind one brick is a stalled run, not a busy one.
- **Is the supervisor alive?** The driver is a process and processes die; the supervisor
  restarts it and gives up after repeated immediate failures.
- **What did the loop say when it stopped?** It quarantines a bad task and carries on. It
  stops itself only for hours of work with nothing accepted.

A run that produced nothing is usually a backlog being debugged, and that is the cheapest
place to find out.
