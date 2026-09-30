---
name: dashboard
description: Use when the person asks to open, show or check the graph-loop dashboard, which graph-loop loops are running, or which specs of the current project are built, being built or waiting. Shows that project's dashboard once and says how to keep it open live. It is read-only and never starts, stops or edits a loop.
---

# Showing a project's graph-loop dashboard

The dashboard is optional and read-only. It lists the lean loops running on this machine and, for one
project, every spec with a mark: built, building, stopped, pull request open or waiting.

## 1. Find graph-loop

Use the checkout this plugin was installed from, as the `run` skill's section 1 says; call it `$GL`.
If `$GL/graph/loops.sh` does not exist, this checkout predates the dashboard: say so, tell the person
to run `git pull` in `$GL`, and stop.

## 2. Find the project

The top of the git repository the person is in: `git rev-parse --show-toplevel`. If they named another
project, use that folder. If it has no `docs/lean`, say so and stop; do not guess what they want.

## 3. Show it once

```bash
bash $GL/graph/loops.sh -1 <project>
```

Put its output in front of the person. For only part of it, run `loops.py` with a filter instead:

```bash
python3 $GL/graph/loops.py <project> --only built       # what is built
python3 $GL/graph/loops.py <project> --only open        # what is left
python3 $GL/graph/loops.py <project> --only attention   # stopped, or a pull request waiting for them
```

## 4. Say how to keep it open

A live, refreshing screen cannot run inside this conversation. Give the person the command with the real
paths filled in, to run in their own terminal (in Claude Code, type `!` before it):

```bash
bash $GL/graph/loops.sh <project>
```

Its keys: a digit switches to that loop, `f` cycles the filter, `q` quits. It refreshes every 15 seconds.

## 5. Stay read-only

Never start, stop or edit a loop, a spec or a workspace from this skill. To run a loop, use the `run` skill.

## A fault in graph-loop itself

If a screen or command here shows something wrong or misleading, file an issue at
https://github.com/cocodedk/graph-loop/issues (`gh issue create --repo cocodedk/graph-loop`), search
first, and give it one label: `P0` loses or corrupts work or leaks something private, `P1` a gate or
review can be skipped, `P2` wrong output with a way round, `P3` a rough edge. The repository is public,
so leave out names, paths and accounts from the project you were working on, and show the person the
text before filing unless they told you to file on your own.
