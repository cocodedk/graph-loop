# 02: a list of the lean loops that are running

## What the owner wants

One place that says which graph-loop lean loops are running on this machine and what each is doing,
so the person can tell at a glance, without opening any project. It is optional: nothing starts it,
no loop needs it, and a project that never uses it is not touched. This step is the list. Opening one
loop in detail, the live screen and the card loop come in later specs.

## The command

`python3 graph/loops.py` prints the list once and exits with status 0. It only reads: it writes no
file and starts nothing. Its logic sits in modules under `graph/lib/` (the entry file only parses
arguments and prints), each under the 200-line cap.

## What counts as a running loop

A process whose command is a Python interpreter (its first word's file name starts with `python`)
running a script whose path ends in `/lean.py` or is exactly `lean.py`, given the arguments
`--workspace`, `--repo` and `--spec`. A shell that only mentions `lean.py` inside a longer command line
does not count. The process list is read with `ps -eo pid,etimes,args`, and each process's working
directory from `/proc/<pid>/cwd` (Linux only, and marked with a `# ponytail:` comment that says so and
names the upgrade path).

Relative `--workspace` and `--repo` paths are resolved against that working directory. The **project**
is the last part of the resolved `--repo` path. The **spec** is `--spec`'s file name without `.md`.

## The list

One line per running loop, oldest first by process id, numbered from 1:

```
1  sitrep           01-capture-core   grilling  2m10s   loop up 31m
2  fits-api         02f-routes        building  12m03s  loop up 45m
```

Columns, in order: the number; the project; the spec; the **step**; how long the loop has been in that
step; and `loop up` with the process's age. Columns are padded to the longest value in their column
plus two spaces. Durations show seconds under a minute (`45s`), minutes and seconds under an hour
(`2m10s`), and hours and minutes above (`1h05m`).

With no loop running the command prints `no lean loops running`.

## The step

Read from the last line of the loop's event log, `<workspace>/events.jsonl` (the workspace path from
`--workspace`; its lines are JSON objects with an `at` time like `2026-09-28T19:36:22Z`, in UTC, and a
`kind`):

- the last event is `lean_call_started` (spec 01 adds it): the step is `grilling`, `building` or
  `reviewing` for its `purpose` of `grill`, `build` or `review`, and the time in the step is the time
  since that event's `at`;
- any other last event, or a `purpose` it does not know: `working`, with the time since that event;
- no event log, or an empty one: `starting`, with the time since the process started.

A line of the log that is not valid JSON is skipped. A loop whose workspace cannot be read still
appears, as `starting`.

## Done when

The driver's and the slicer's tests pass, and new tests, with no real process, clock or loop (the
process list, the working directories, the clock and the event logs are passed in or faked), prove:

1. Which processes count: an interpreter running `lean.py` with the three arguments counts, including
   through a relative path; a shell whose command line only contains the text does not; a `lean.py`
   without `--spec` does not.
2. The project and the spec names, with absolute and relative `--repo`, `--workspace` and `--spec`.
3. Each step: the three `lean_call_started` purposes, another last event, an unknown purpose, no
   event log, an empty one, and a log with a broken line.
4. The duration format at 45 seconds, 2 minutes 10 seconds, 1 hour 5 minutes and exactly one minute.
5. The line layout with two loops of different name lengths, the numbering, the order, and the
   message for no loops.
6. The command writes nothing and exits 0, and `graph/loops.py` is under the cap with its modules.
7. Every earlier test still passes, unchanged. The builder adds new test files as the checks above
   need.

## Out of scope

Opening one loop in detail, marking specs as built, filters, a live screen, the card loop, and any
change to the lean loop itself.
