---
name: run
description: Use when the person says "use graph-loop", "build this with graph-loop", "let the loop do it" or "run the lean loop" on a project. Sets up and runs graph-loop's lean loop (graph/lean.py), which works one spec per feature, gates each feature on the project's own suite, has a second model review every diff, and lands each feature on local main. For writing card backlogs instead, use the graph skill.
---

# Running graph-loop on a project

The lean loop takes one spec file per feature, in order. For each spec, one Claude
builder works in a fresh worktree off `main`. The project's suite is the gate, and a
Codex reviewer reads the diff. After up to two repair passes, the feature lands on
local `main`. The first feature that fails to land stops the run, because later
specs build on it. You set the run up; the loop does the building.

## 1. Find graph-loop

Use the checkout this plugin was installed from; `claude plugin marketplace list`
shows its path. With no checkout, run
`git clone https://github.com/cocodedk/graph-loop`. Below, `$GL` is that checkout.

The builder is `claude` and the reviewer is `codex`; both must be on `PATH`.
`GRAPH_CLAUDE` and `GRAPH_CODEX` override the binaries.

## 2. A workspace and a proven contact

The workspace holds the run's log, its claims and its contact. Put it somewhere git
ignores, for example `<repo>/scratchpad/lean/`. Mail goes through
`$GL/graph/lib/smtp.env`, which is never committed. It needs `SMTP_HOST`,
`SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` and `SMTP_TO`. Ask the person to
fill it in, and never read its values back to them.

```bash
python3 $GL/graph/graph-goal.py --workspace <ws> contact "<their email>"
```

This sends a test mail and records the address. Ask the person whether it arrived.
Without a proven contact, `lean.py` refuses to start.

## 3. A profile, proven on main

Copy the closest file from `$GL/profiles/` into the repository as
`profile-<name>.md` and link it from the repository's `CLAUDE.md`, or pass it with
`--profile`. Under `## suite_command`, `## build_command` and `## artifact`, the loop
reads the first indented line of each.

Before any spec, run the suite on `main` the way the loop will run it: from a clean
checkout, with a scrubbed environment and an empty `HOME`. It must pass. A suite that
only passes in your own shell fails every feature for reasons no builder can fix.
Leave slow, flaky or paid tests (live model calls) out of the gate.

## 4. One spec per feature

Write one markdown file per feature: its goal, its behaviour, its acceptance tests,
and what is out of scope. Settle every decision the builder would otherwise guess.
Order the specs so each builds only on the ones before it. Keep them in the
repository, for example `docs/lean/NN-name.md`. If the repository's own rules would
stop an autonomous builder (for example "ask a person at every step"), the person
must write an exception for the loop into those rules and merge it to `main` before
the run.

## 5. Run

```bash
python3 $GL/graph/lean.py --workspace <ws> --repo <repo> \
  --spec docs/lean/01-first.md --spec docs/lean/02-second.md [--profile <file>]
```

Before building anything, a reviewer reads all the specs:

- **Exit 2:** its questions have been emailed and nothing was built. Answer them in
  the specs, then run again.
- **Exit 0:** every spec landed, `main` was built, and the person got a
  "ready to accept" mail naming the artifact.
- **Exit 1:** a feature did not land, or the build on `main` was red. The mail says
  which. Read the workspace log before changing anything.

Runs take hours, so run it in the background.

## After the run

The loop lands on local `main` with `git commit-tree`, so the repository's commit
hooks never run on its commits. Run the hooks' checks yourself before pushing.
Pushing, and opening any pull request, stays with the person.
