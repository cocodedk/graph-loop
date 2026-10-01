---
name: run
description: Use when the person says "use graph-loop", "build this with graph-loop", "let the loop do it" or "run the lean loop" on a project. Sets up and runs graph-loop's lean loop (graph/lean.py), which builds one spec per run, gates it on the project's own suite, has a second model review the diff, and opens one pull request for the person to review and merge. For writing card backlogs instead, use the graph skill.
---

# Running graph-loop on a project

The lean loop builds one spec file per run. One Claude builder works in a fresh
worktree off origin's `main`. The project's suite is the gate, and a Codex reviewer
reads the diff. After up to two repair passes (none when the builder or reviewer gives no
real answer, such as on a usage limit: that stops the run at once), the work is pushed as the branch
`lean/<feature>` with a pull request; `main` never moves. A green change the reviewer
still refuses after the last repair is pushed too, its findings in the pull request's
description for whoever merges it. The workspace's `spec-<name>.json`
gets `lean_status` (`pr_open` or `stopped`) and `lean_pr` or `lean_worktree`; the spec file is never written. While any
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
reads the first indented line of each. It refuses a profile that lacks one, so add
any the copy does not have.

A project that must spend one Claude account only, such as a personal project on a machine whose
default login is a work account, adds `## account` with that account's name as `GRAPH_ACCOUNTS`
names it, for example `personal`. The loop then spends that account and no other: when it runs out
the run stops, and a name the machine does not configure stops the run before anything is spent.

`GRAPH_ACCOUNTS` belongs to the machine, not the repository: `name=<CLAUDE_CONFIG_DIR>` pairs separated by
commas, exported where the loop is started (a shell profile, or the top of the script that starts it), for
example `export GRAPH_ACCOUNTS=personal=<its config directory>`. Without the pair a profile's `## account`
stops the run at once, naming the account and this variable. Ask the person which login each name means.

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

## 5. Lessons, optional

`lessons.md` beside the specs holds what agents keep rediscovering about this project, one fact per
line with its evidence (a spec, an event or a commit). For example: `- Say which earlier tests the
builder may change (the grill asked three times, specs 06–10).` The grill and the builder read it as
hints to check, never as proof; the reviewer never sees it. People write it, not the loop. Delete a
line that turns out wrong. When a lesson keeps coming back, turn it into a check (a test, or a line
every spec carries) and delete the line.

## 6. Run

```bash
python3 $GL/graph/lean.py --workspace <ws> --repo <repo> --spec docs/lean/01-first.md [--profile <file>]
```

The run first fetches origin. Then, before a spec's first build, a reviewer reads it
(a spec that carries on after a stop is not read again; if its requirements change,
delete its `<ws>/spec-<name>.json` so it starts afresh):

- **Exit 2:** its questions have been emailed and nothing was built. Answer them in
  the specs, then run again. A feature with a user interface is questioned until its
  spec defines the whole journey, every page and state, and names a design to match.
- **Exit 3:** a branch on origin is unmerged, so nothing was built. The mail lists
  the branches. The one exception is the spec's own open pull request with unresolved
  review threads (CodeRabbit's or a person's). Then the run fixes those on the PR's
  branch and pushes to the same PR, so rerun the same spec after a review. The suite
  checks that fix; the reviewer who raised the threads reads it on the PR.
- **Exit 0:** the pull request is open, its branch was built, and the person got a
  "ready for review" mail with the PR link and the artifact.
- **Exit 1:** the feature stopped, or its build was red. The mail says which. A stopped
  feature's worktree is kept and the mail names it; so does its `spec-<name>.json`
  (`lean_worktree`) unless the run was fixing an open pull request. A red build
  leaves its pull request open. Read the workspace log before changing anything.

Runs take hours, so start one detached from your shell tool, never as its background task: the host
stops a background task at its time limit (10 minutes at most) and the loop dies with it, leaving no
stopped event and no mail.

```bash
setsid nohup python3 $GL/graph/lean.py --workspace <ws> --repo <repo> --spec <spec> > <ws>/run.log 2>&1 < /dev/null &
```

Check on it with the dashboard (the `dashboard` skill) or by looking for its process.

## After the run

The loop commits with `git commit-tree`, so the repository's commit hooks never run on
its commits. The pull request's CI is the check. Merging stays with the person; delete
the branch on merge, or it will block the next run.

To watch a running loop, and see which of a project's specs are built, use the `graph:dashboard` skill.

Runs leave their trees in the temp folder. Once specs are merged, `python3 $GL/graph/lean_clean.py --workspace <ws>
--repo <repo>` removes the trees of those specs only, never by age, and prints any it could not remove.

## A fault in graph-loop itself

If graph-loop misbehaves (a wrong verdict, a lost or stuck run, a misleading screen, a skill that
says something the code does not do), file an issue at https://github.com/cocodedk/graph-loop/issues
with `gh issue create --repo cocodedk/graph-loop`. Search first (`gh issue list --repo
cocodedk/graph-loop --search "<words>"`) and comment on a match instead of filing again. Give it one
label, the grade of how bad it is:

- `P0`: the loop loses or corrupts work, leaks something private, or spends without limit.
- `P1`: a gate or a review can be skipped, or a wrong result is accepted as right.
- `P2`: wrong or misleading output, or a step wastes time or money, and there is a way round it.
- `P3`: a rough edge: wording, layout, a small inconvenience.

Write what happened, why it matters and what you saw, with the numbers. The repository is public:
leave out names, paths, accounts and identifiers from the project you were working on. File only what
you can show, not a guess. Show the person the text first and file it when they agree, unless they
have told you to file on your own.
