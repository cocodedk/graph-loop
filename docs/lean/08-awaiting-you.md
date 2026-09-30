# 08: a project that waits for a person stays on the dashboard

## What the owner wants

When the grill has questions and nobody has answered them, the loop exits (it mails the questions and
stops), and the project disappears from the dashboard: the list shows running processes only, and only
the project view carries the `? question` mark. The same happens when a build stops or its pull request
is open and nobody has merged it. The owner asked on 30 September 2026 that the dashboard says such a
project is awaiting an answer, and that the loop must not seem to have disappeared.

## What the loop records

When `graph/lean.py` starts, before it spends anything, it records the absolute folder of its `--repo` as
one line in the text file `graph-loop/projects` inside the user's standard state folder
(`$XDG_STATE_HOME`, or `~/.local/state` when that is unset or empty; the folder is created when
missing). A folder already on a line is not added again; the other lines stay as they are, in their order.
A file that cannot be written does not stop the run. Nothing else in the loop changes, and no new
environment variable is added.

## What the list shows

`graph/loops.py`'s list (the plain list, and the first block of `--screen`) gets, after the running loops,
a block for the projects in that file:

- A project is in the block when it has no running lean loop (by its `--repo`, resolved as the project
  view resolves it) and at least one spec in `docs/lean` that needs a person: `lean_status` is `questions`,
  `stopped` or `pr_open`, judged by the same rule the project view uses for its marks
  `? awaiting answer`, `✖ stopped` and `● pr open`. A spec the merged history shows as built is not one.
- One line for each such spec, in the project's folder-name and spec order: `<project>  <spec>  awaiting
  answer` (or `stopped`, or `pr open`), with the same column alignment as the loop lines.
- The block has a heading line `waiting for you:` and is left out when it would be empty. With no loop
  running and nothing waiting, the list still says `no lean loops running` alone; with no loop running and
  something waiting it says `no lean loops running`, a blank line and the block.
- A recorded folder that no longer exists, has no `docs/lean`, or cannot be read is skipped without a word.

## The mark

The project view's mark `? question` reads `? awaiting answer` in every place it is printed (the spec
lines, the first line's counts and the filters that pass it), padded like the other marks. The filter
`attention` still passes it.

## Every screen

The live screen (spec 04) prints the new block as part of the list, and the shrinking of spec 05 counts its
lines with the list's lines: they are fixed lines and are never cut. The colours of spec 06, when they exist,
give the block's heading bold and its lines the colour of their mark; this spec adds none of its own.

## Edges

- Two spec files of one project in the block are two lines. Ten projects are ten blocks of lines; there is
  no limit.
- The keys of spec 04 (`1`-`9` switch a running loop) do not reach the block's lines.
- A project recorded twice through two spellings of its folder (a symlink) is listed once, by its resolved
  path.
- Reading the file and the specs writes nothing and starts nothing.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. A start of `lean.py` (with the state folder faked through `XDG_STATE_HOME`) writes the repo's folder once,
   keeps the other lines and order, does not add a folder twice, creates the missing folder, and still runs
   when the file cannot be written.
2. The list's block names each of the three kinds (asked, stopped, pr open) with the words above, skips a
   project with a running loop, a folder that is gone, one without `docs/lean` and a spec the history shows
   built, and is left out when empty.
3. With no loop running and something waiting, the list is `no lean loops running`, a blank line and the
   block; with nothing waiting it is the single line it is today.
4. `? question` reads `? awaiting answer` in the spec lines, the counts and the filters, aligned like the
   other marks.
5. `--screen` prints the block and the height shrinking of spec 05 counts it; `--once` prints it too.
6. Nothing is written and nothing started by the dashboard's reading, and the files stay under the cap.
7. Every earlier test still passes. The builder may change any earlier test whose expectation this spec
   changes (the word `question` in the marks, the list when nothing runs but something waits), and nothing
   else in them. The builder adds new test files as the checks above need.

## Out of scope

Mail, a web page, forgetting a project, a setting to name the projects, and any change to what the loop
does when the grill asks.
