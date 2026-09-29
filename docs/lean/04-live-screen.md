# 04: a live screen to switch between loops

## What the owner wants

One screen that keeps itself up to date, lists the running loops, shows the selected project's specs
with their marks, and lets the person switch between loops and filter with one key. Optional, like
everything before it: nothing needs it and no loop starts it.

## The command

```
bash graph/loops.sh [project-folder]      live, refreshing every 15 seconds
bash graph/loops.sh -1 [project-folder]   one look and stop
```

`graph/loops.sh` is a small shell script in the style of `graph/watch.sh`: it clears the screen,
prints, waits and prints again; all reading lives in Python under `graph/lib/`. It calls `python3
graph/loops.py` (or the command in `LOOPS_CMD`, which the tests use to fake it), with these two new
options of `graph/loops.py` that this spec adds:

- `--screen [<project-folder>] [--only <filter>]` prints the whole screen: the list of spec 02, a
  blank line, the project view of spec 03 for the folder given (or, with none given, for the first
  running loop whose project folder can be resolved; with no loop running and none given, only the
  list's message `no lean loops running`), a blank line, and the key line below. The key line is always
  printed, so `f` and `q` work with no loop.
- `--path <N>` prints the folder of loop number N from the list, and nothing when there is no such loop
  or its project folder cannot be resolved (spec 02's `?`).
- `--refresh <seconds>` (15 when absent) is only what the key line says: `every <seconds>s`.
- `--once` leaves out the key line and the blank line before it, since a single look takes no keys. `-1`
  passes it.

The key line reads `keys: 1-9 switch loop · f filter (<current filter>) · q quit · every <N>s`, where
the filter is `all`, `built`, `open` or `attention` and N is `LOOPS_REFRESH` (below), passed as
`--refresh`.

## The keys

The script holds two things between refreshes: the selected project folder (from `[project-folder]`, or
none, meaning the first running loop) and the filter (`all` at first). It waits for a key for the refresh
time (`LOOPS_REFRESH` seconds, 15 by default) and reads it from standard input:

- a digit `1` to `9`: selects the folder that a fresh `--path <digit>` prints at the moment of the
  keypress, not the one shown beside that number on the last screen (the numbers can have moved in
  between; the screen printed next shows which project was selected); when it prints nothing the
  selection stays as it was;
- `f`: the filter moves on, `all`, `built`, `open`, `attention`, and back to `all`; `all` passes no
  `--only`;
- `q`, or Ctrl-C: prints `stopped watching.` and exits with status 0;
- any other key, or no key: refreshes.

A selected folder stays selected when its loop ends, so the person keeps seeing its specs.

## Edges

- Only loops 1 to 9 can be reached by a key; a tenth loop is listed but not selectable (`# ponytail:`
  one key, a prompt for a number later). The digit `0` counts as any other key.
- A selected folder that is not a project prints spec 03's `not a project with docs/lean: <path>` line
  where the project view would be, and the screen goes on refreshing.
- The live screen clears the terminal before each print, as `watch.sh` does; `-1` does not clear.
- Keys are read from standard input whatever it is, a terminal or a pipe: piped keys are processed one
  by one until the input ends, and at the end of input the script behaves as if `q` was pressed.
- Each refresh builds the whole screen first, then clears and prints it in one go, so the person never
  sees an empty screen. A key pressed while `loops.py` is still running is not lost: it is read at the
  next wait.
- If `graph/loops.py` exits with a non-zero status (for example `cannot read the process list`), its
  output is shown as it is and the live screen keeps refreshing; with `-1` the script exits with that
  same status.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. `--screen` prints the parts in the order above, for a given folder, for none given with two loops,
   and for none given with no loop; `--path` for a number that exists and one that does not.
2. `-1` prints one screen without the key line (`--once`) and exits with status 0, passing the folder
   and no filter; `--once` on its own, with and without loops.
3. With `LOOPS_CMD` faked and `LOOPS_REFRESH` set short, keys piped in: a digit switches the folder, a
   digit with no loop keeps it, a digit selects the folder a fresh `--path` gives even when the last
   screen showed another for that number, `f` cycles through the four filters and back, an unknown
   key only refreshes, and `q` ends with `stopped watching.` and status 0.
4. Each edge above: a tenth loop, `0`, a folder that is not a project, piped keys and end of input, a
   failing `loops.py` live and with `-1`, the key line with no loop and with a `LOOPS_REFRESH` other
   than 15, and a first loop whose folder cannot be resolved (skipped for the default view; `--path`
   prints nothing).
5. The script and its Python stay under the cap, and it starts nothing and writes nothing.
6. Every earlier test still passes, unchanged. The builder adds new test files as the checks above
   need.

## Out of scope

The card loop, a web page, mouse support, and any change to the lean loop itself.
