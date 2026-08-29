# Project rules

## What this repository is

A driver that works a backlog of atomic tasks to done, and the writing that
explains how to build one. Two models that never trust each other: a reviewer
refuses any task whose gate could pass without the work, a builder does one task
in a private worktree, a gate command's exit code is the verdict, a fresh
reviewer reads the finished diff, and only then is the work committed.

**The runtime is not here yet.** This repository currently carries the design,
the diary and the skill. The code arrives later, in one piece, from a source that
has stopped moving. Do not partially import it; a half-moved loop is worse than
none, because the half that runs is the half nobody reads.

## Nothing local travels

This repository is public and the loop it carries was built inside private work.
No account name, home directory, machine path, foreign commit hash or task
identifier from that work belongs in a tracked file — not in code, not in a
comment, not in a filename, not in a commit message.

`scripts/scrub-check.sh` enforces the half of this that can be written down as a
shape. It ships structural patterns only, so it contains no literal it forbids
and scans itself like every other file. The literals of one migration live in a
private denylist passed by path, which never enters this repository.

It reads tracked contents, tracked filenames **and the full history**, because a
clean working tree proves nothing if the commit before it still names something.
If it fails, fix the file. Never the check.

## Writing

- Plain language. The reader gets what they need, can find it, and can use it.
  Prefer the common word to the rare one.
- An incident survives if a stranger can learn from it without learning anything
  about us. Keep the mechanism and the numbers; drop the names.
- The numbers stay. Costs, timings, how many review rounds something took — they
  are what makes a rule believable, and they identify nobody.

## Code

- The simplest thing that works. Before writing, ask in order: does this need to
  exist, is it already here, does the standard library do it, does the platform
  do it, can it be one line. Stop at the first yes.
- No file over 200 lines. A file that outgrows it splits at a natural seam and
  the old name stays as the front door.
- PyYAML is the only runtime dependency. A second one needs a reason in the pull
  request.
- Fix a bug at its root: one guard in the shared function, after reading every
  caller.
- A new check is not trusted until the case it exists to catch has been made to
  fail in front of you. This is not a style preference — the guard in this
  repository caught its own pattern file the first time it was run properly, and
  that is the only reason it works now.

## Two rules this project bought the hard way

- **A document is not authority about the code.** The design this loop shipped
  with claimed the logic was generic; four places in the source said otherwise,
  including one that copied a private directory into every worktree it made. A
  claim of genericness is a measurement, not a statement, and the measurement is
  a grep of the source — spelled the way the source spells it.
- **Take the inventory from the repository, not from the document.** A file list
  written by hand drifts from the tree it describes. `git ls-files` does not.

## Git

- Conventional Commits, enforced by a hook.
- Never commit to `main` directly; open a pull request.
- Never `--no-verify`. A failing hook means fix the cause.
- Never force-push `main`.
