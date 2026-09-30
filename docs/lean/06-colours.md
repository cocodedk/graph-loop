# 06: colours on the live screen

## What the owner wants

The live screen (`bash graph/loops.sh`) uses colour so the eye finds what matters: which specs are
built, running, stopped or waiting for a person, what is getting expensive, and a build that has gone
quiet. The owner asked for this on 30 September 2026. Spec 05 (the screen fits the terminal) comes
first and is not changed here.

## The option

`graph/loops.py` gains `--color`. With it, the text it prints is the same text with ANSI colour codes
added, so with the codes removed it is byte for byte the text it prints without the option. Without it
nothing changes. Padding and alignment are made on the plain text first and the codes added after, so
columns line up as before.

## The colours

Only the eight basic ANSI colours and bold and dim, so any terminal shows them:

- **Marks:** `✔ built` green, `▶ building` yellow, `✖ stopped` red, `? question` magenta,
  `● pr open` cyan, `· waiting` dim (the whole line of a waiting spec is dim).
- **Project first line** (`name  N specs: …`) bold; the word `loop:` lines bold up to the step name.
- **Cost** in a spec line: yellow when above $3.99, red when above $8, no colour otherwise; the date, the
  turns and the model are dim.
- **`last step … ago`** on a loop line: no colour up to 5 minutes, yellow from 5 minutes up to 15, red at
  15 minutes and beyond. A step that is `testing` or `checking the build` for 15 minutes or more is red
  too (its time is the loop line's own time).
- **The loop list** (the first block): the step name follows the same yellow and red thresholds when it
  has run 15 minutes or more (red); `loop up …` is dim.
- **The key line** dim; the `recently merged:` heading bold, its lines dim.
- The shrink lines of spec 05 (`… N more`) take the colour of their mark.

## The script

`graph/loops.sh` passes `--color` when standard output is a terminal and the environment variable
`NO_COLOR` is unset or empty; it passes it on the live screen and with `-1`. Otherwise it passes
nothing, so a captured screen or a pipe stays plain text.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. With `--color`, stripping the ANSI codes from the output leaves exactly the output without it, for
   the list, the project view and the whole screen.
2. Each mark carries its colour; the whole waiting line is dim; a cost above $3.99 is yellow and above
   $8 red, and one at or below $3.99 has none.
3. `last step … ago` and a long `testing` step take the thresholds above at their edges (299 s, 300 s,
   899 s, 900 s).
4. Without `--color` there is no escape character anywhere in the output.
5. `graph/loops.sh` passes `--color` on a terminal (faked) with `NO_COLOR` unset or empty, and passes it
   with neither a non-terminal output nor a non-empty `NO_COLOR`.
6. Every earlier test still passes. The builder may change any earlier test whose expectation this
   spec changes (the exact arguments `graph/loops.sh` passes to `LOOPS_CMD`, and the tests that count
   files), and nothing else in them. The builder adds new test files as the checks above need.

## Out of scope

A theme setting, 256-colour or truecolour, background colours, and any change to what is shown or to
the lean loop.
