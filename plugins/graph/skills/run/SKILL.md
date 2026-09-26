---
name: run
description: Use when the person says "use graph-loop", "build this with graph-loop", "let the loop do it" or "run the lean loop" on a project. Sets up and runs graph-loop's lean loop (graph/lean.py), which builds one spec per run, gates it on the project's own suite, has a second model review the diff, and opens one pull request for the person to review and merge. For writing card backlogs instead, use the graph skill.
---

# Running graph-loop on a project

The lean loop builds one spec file per run. One Claude builder works in a fresh
worktree off origin's `main`. The project's suite is the gate, and a Codex reviewer
reads the diff. After up to two repair passes, the work is pushed as the branch
`lean/<feature>` with a pull request; `main` never moves. The spec file's front matter
gets `lean_status` (`pr_open` or `stopped`) and `lean_pr` or `lean_worktree`. While any
branch on origin is unmerged, the loop's own or anyone's, the run builds nothing. So
the next spec waits until the person has merged (or deleted) every open branch. You set
the run up; the loop does the building.

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
Run them in order, one per run, each after the previous pull request is merged. Keep them in the
repository, for example `docs/lean/NN-name.md`. If the repository's own rules would
stop an autonomous builder (for example "ask a person at every step"), the person
must write an exception for the loop into those rules and merge it to `main` before
the run.

## 5. Run

```bash
python3 $GL/graph/lean.py --workspace <ws> --repo <repo> --spec docs/lean/01-first.md [--profile <file>]
```

The run first fetches origin. Then a reviewer reads the spec before anything is built:

- **Exit 2:** its questions have been emailed and nothing was built. Answer them in
  the specs, then run again.
- **Exit 3:** a branch on origin is unmerged, so nothing was built. The mail lists
  the branches. The one exception is the spec's own open pull request with unresolved
  review threads (CodeRabbit's or a person's). Then the run fixes those on the PR's
  branch and pushes to the same PR, so rerun the same spec after a review.
- **Exit 0:** the pull request is open, its branch was built, and the person got a
  "ready for review" mail with the PR link and the artifact.
- **Exit 1:** the feature stopped, or its build was red. The mail says which, and the
  spec's front matter names the kept worktree. Read the workspace log before changing
  anything.

Runs take hours, so run it in the background.

## After the run

The loop commits with `git commit-tree`, so the repository's commit hooks never run on
its commits. The pull request's CI is the check. Merging stays with the person; delete
the branch on merge, or it will block the next run.
