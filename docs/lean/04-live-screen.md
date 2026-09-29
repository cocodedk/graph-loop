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
  running loop's project; with no loop running and none given, only the list's message), a blank line,
  and the key line below.
- `--path <N>` prints the folder of loop number N from the list, and nothing when there is no such loop.

The key line reads `keys: 1-9 switch loop · f filter (<current filter>) · q quit · every 15s`, where the
filter is `all`, `built`, `open` or `attention`.

## The keys

The script holds two things between refreshes: the selected project folder (from `[project-folder]`, or
none, meaning the first running loop) and the filter (`all` at first). It waits for a key for the refresh
time (`LOOPS_REFRESH` seconds, 15 by default) and reads it from standard input:

- a digit `1` to `9`: selects the folder that `--path <digit>` prints; when it prints nothing the
  selection stays as it was;
- `f`: the filter moves on, `all`, `built`, `open`, `attention`, and back to `all`; `all` passes no
  `--only`;
- `q`, or Ctrl-C: prints `stopped watching.` and exits with status 0;
- any other key, or no key: refreshes.

A selected folder stays selected when its loop ends, so the person keeps seeing its specs.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. `--screen` prints the parts in the order above, for a given folder, for none given with two loops,
   and for none given with no loop; `--path` for a number that exists and one that does not.
2. `-1` prints one screen and exits with status 0, passing the folder and no filter.
3. With `LOOPS_CMD` faked and `LOOPS_REFRESH` set short, keys piped in: a digit switches the folder, a
   digit with no loop keeps it, `f` cycles through the four filters and back, an unknown key only
   refreshes, and `q` ends with `stopped watching.` and status 0.
4. The script and its Python stay under the cap, and it starts nothing and writes nothing.
5. Every earlier test still passes, unchanged. The builder adds new test files as the checks above
   need.

## Out of scope

The card loop, a web page, mouse support, and any change to the lean loop itself.
