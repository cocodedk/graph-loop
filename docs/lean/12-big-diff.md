# 12: a diff over the reviewer's input limit is shortened, not refused

## What the owner wants

The reviewer of a lean change gets the whole diff in its prompt. When that diff is huge, Codex refuses
the input in about a second ("Input exceeds the maximum length of 1048576 characters") and the run stops
with no review at all. A repair round that regenerates big generated files does it: a change of +436 lines
can be a 2 MB diff. This is the second half of issue #224, graded `P2` (the first half, the crash text,
was fixed by spec 11); the owner asked on 30 September 2026 that the loop build it.

## What changes

`judge()` in `graph/lean_judge.py` measures the prompt it is about to send. Below the limit, nothing
changes: the prompt is byte for byte what it is today, a first build's and a revise round's alike.

When the prompt is over `PROMPT_LIMIT` (900000 characters, a constant in that module, under Codex's limit
with room for its own framing), the diff inside it is replaced by:

1. **A stat block:** one line per changed file with its name and its lines added and removed, for every
   file in the diff.
2. **The diff sections of whole files**, smallest first, added one file at a time while the prompt stays
   within the limit. A file's section is never cut in the middle: it is in whole or not at all.
3. **A `Not shown` list** of each file left out, with the size of its section, and one sentence telling the
   reviewer that these files were too large to include and that it can read them in its worktree.

A single file whose section alone is more than the budget is not shown and is named in the list. The
threads section of a revise round, the spec and the answer rule are never cut.

## Answers to the grill

- **When the parts that are never cut already exceed the limit** (the spec, the threads and the answer rule
  alone, or with the stat block and the `Not shown` list after every diff section is left out): the stat
  block and the `Not shown` list are shortened, in this order: the stat block keeps the files with the most
  lines changed first, as many as fit, then one line `... and N more files` (N exact); the `Not shown` list
  becomes the same kind of line, `N files not shown`. The spec, the threads and the answer rule are never
  cut.
- **When even those never-cut parts alone exceed the limit,** nothing more is shortened: the prompt is sent
  as it is and Codex refuses it, exactly as today, and the run stops with the real error in its stop text
  (spec 11). The test for this case only checks that `judge()` does not loop, raise or cut the spec.

## Edges

- The diff is read as the text it is: its `diff --git` lines start each file's section; a diff with no such
  line (a rename-only note, empty) is treated as one section.
- Files are ordered by the size of their section, smallest first, ties by name.
- No call to git, no setting, no new environment variable. The project's own `.gitattributes` (for
  example `-diff` on generated files) already shortens a diff before it gets here; that is left to it.
- Every Python file stays at or under 200 lines.

## Done when

The driver's and the slicer's tests pass, and new tests prove (fake the reviewer; no real model):

1. A diff whose prompt fits is sent byte for byte as before, for a first build and for a revise round.
2. A large diff gives a prompt of at most `PROMPT_LIMIT` characters holding the stat block for every file,
   the whole sections of the smallest files that fit, and the `Not shown` list with sizes.
3. No file's section is cut in the middle: each shown section equals the original section.
4. A file bigger than the budget by itself is in the not-shown list, and the other files that fit are shown.
5. The stat block's added and removed counts match the diff.
6. Every earlier test still passes. The builder may change any earlier test that pins the judge prompt's
   diff heading for an oversized diff, and nothing else in them. The builder adds new test files as the
   checks above need.

## Out of scope

Reviewing per file in several calls, a setting for the limit, `.gitattributes` handling, and the crash text
(already done).
