# 05: the live screen fits the terminal

## What the owner wants

The live screen (`bash graph/loops.sh`) shows everything that needs a look without scrolling. Today a
project of 48 specs prints 48 spec lines, so the running loop and the specs that need a person scroll
out of view. The owner asked for this on 30 September 2026.

## The option

`graph/loops.py --screen` gains `--rows <N>`: the height of the terminal in lines. With it, the whole
screen printed (the loop list, the project view and the key line) is at most `N - 1` lines. Without it
nothing changes: every existing output stays as it is, byte for byte, and `--rows` with `--once` or
with a project view alone (no `--screen`) is ignored.

## How the project view shrinks

The list of loops and the key line keep their lines. The project view, whose first line and loop lines
stay too, gets what is left, and when its spec lines and its `recently merged` block do not fit:

1. The `recently merged` block goes first, whole.
2. A spec that is building, stopped, asked (`? question`) or has a pull request open always stays, one
   line each, in file order.
3. The built specs become one line: `✔ built     … 15 more` (the mark as today, then `…`, the count,
   `more`), when there is any.
4. The waiting specs stay in file order as many as fit, then one line `· waiting   … 20 more` for the
   rest, when any are left out. When they all fit, no such line.
5. When even the specs of rule 2 do not fit, they all still print and the screen is taller than `N - 1`;
   nothing that needs a look is ever cut.

The filter (`--only`) works first: only the specs it passes are counted, shrunk and shown. When they
all fit, they print as today.

## The script

While it is live, `graph/loops.sh` reads the terminal's height with `tput lines` before each refresh
(where its output is still the terminal, not inside the captured command) and passes `--rows <height>`
to `--screen`. It passes nothing when `tput` prints nothing, and `-1` never passes it.

## Every screen

The first line of the project view (its counts), the `loop:` lines and their order do not change.

## Answers to the grill

- **The fixed parts overflow** (the loop list, the project's first line and loop lines, and the key line
  are already more than `N - 1` lines, or the specs of rule 2 push it over): nothing that needs a look and
  no fixed line is ever cut, so the screen is taller than `N - 1`. Then every optional line is
  dropped except the two count lines: `recently merged` goes, no waiting spec prints, and the
  `✔ built     … N more` and `· waiting   … M more` lines still print, when there is anything built or
  waiting, however tall that makes the screen.
- **Room for some waiting specs:** with `F` lines left after the fixed parts, the specs of rule 2 and
  the built line, all `W` waiting specs print when `W <= F`; otherwise the first `max(0, F - 1)` print and
  the `… M more` line takes the last of the room (`M` is the number left out).

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. With `--rows` smaller than the project view, the printed screen has at most `N - 1` lines, and the
   stopped, question, pr open and building specs are all there.
2. The built specs are one `✔ built     … N more` line with the right N, and the waiting ones stay in
   file order up to the room with a right `· waiting   … M more` line; when they all fit there is no
   such line, and when nothing is built there is no built line.
3. `recently merged` is dropped when the specs and it do not both fit, and kept when they do.
4. When the specs of rule 2 alone are taller than the screen, all of them print, and when the fixed
   parts overflow, only the two count lines remain of the optional ones (the answers above).
5. With `--only`, the shrinking counts only the specs the filter passes.
6. Without `--rows`, and with `--once`, the output is byte for byte what it is today.
7. `graph/loops.sh` passes `--rows` (the height `tput lines` gives, faked in the test) to the command
   on every live refresh, passes nothing when `tput` gives nothing, and does not pass it with `-1`.
8. Every earlier test still passes. The builder may change any earlier test whose expectation this
   spec changes (the exact arguments `graph/loops.sh` passes to `LOOPS_CMD`, and the tests that count
   files), and nothing else in them. The builder adds new test files as the checks above need.

## Out of scope

Colours (spec 06), a wider layout in columns, resizing between refreshes beyond reading the height at
each one, and any change to the lean loop.
