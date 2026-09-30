# 13: a profile may name a lint command, run after the suite

## What the owner wants

A lean run's gate is the profile's `suite_command`. A build the suite passes and the reviewer accepts can
still fail the project's CI on a lint rule, because the gate cannot run the linter. On one afternoon four
of the last eleven builds of this repository reached CI red on lint only (import order three times, an
unused variable, a `preexec_fn` rule); each needed a small hand-made commit and a CI rerun, and the builder
never learned, because a repair pass only runs for a red suite or a reviewer refusal. This is issue #244,
graded `P2`; the owner asked on 30 September 2026 that the loop build it.

## What changes

- **The profile may hold a `lint_command`.** `graph/lean.py` reads an optional `## lint_command` heading
  like `## account`: the first indented line under it is the command. A profile without it is valid and
  behaves exactly as today; a profile with the heading but no indented line under it is the same as
  without it.
- **The loop runs it after the suite.** In `check()` of `graph/lean_run.py` (or a module it calls), when
  the profile has a `lint_command` and the suite has passed, the loop runs the lint command in the same
  worktree, with the same scrubbed environment, masking and timeout as the suite, before the reviewer is
  asked.
- **A red lint is a red suite.** A lint command that exits non-zero gives the reason
  `the lint is red (<command>):` followed by its output, which starts a repair round exactly as a red suite
  does: the builder is handed that reason, the repair limit of two applies, the reviewer is not asked for
  that round, and a round that changes nothing stops the run as today. The output is cut to its last 2000
  characters in the reason, as the suite's is.
- **A green lint changes nothing**: the reviewer is asked as today.
- **A `lean_lint` event** is written for every lint run, with `task`, `round`, `passed` and the output's
  last 2000 characters, beside `lean_suite`.
- **The builder's prompt** says, when the profile has a lint command, that the lint runs after the suite and
  what it is, so the builder runs it itself when its permissions allow.

## Edges

- The lint runs only when the suite passed; a red suite is handled first and unchanged.
- A revise round (spec 09) runs it too, before the reviewer.
- The command is run as the suite's command is: nothing new is granted to the builder, and no new
  environment variable is added.
- Adding a `## lint_command` line to this repository's own profile (`profile-graph-loop.md`) is a separate
  step, done after the command is checked to run in the scrubbed environment; this spec does not edit that
  file.
- `graph/lean_run.py` stands at 180 lines and no Python file may pass 200: move code to a module and keep
  every name a test patches (`build`, `judge`, `grill`, `masked`, `check`) importable from `lean_run`.

## Done when

The driver's and the slicer's tests pass, and new tests prove (fake the suite, the lint, the reviewer and the
builder; no real model):

1. A profile with `## lint_command` and one indented line yields that command; a profile without the heading,
   or with the heading and no indented line, yields none and is not an error.
2. With no lint command, `check()` behaves exactly as before for a green suite, a red suite and a refusal.
3. With a lint command and a green suite, a green lint lets the reviewer be asked; a red lint returns the
   reason with the command and its output, does not ask the reviewer, and writes a `lean_lint` event with
   `passed` false.
4. A red lint starts a repair round that the builder is handed the reason in, bounded by the repair limit of
   two; a repair that changes nothing stops the run.
5. The lint output in the reason is cut to its last 2000 characters; a shorter output is whole.
6. A red suite never runs the lint.
7. The builder prompt names the lint command when there is one and is unchanged when there is none.
8. Every earlier test still passes. The builder may change any earlier test that pins the exact fields the
   profile reader accepts, and nothing else in them. The builder adds new test files as the checks above
   need.

## Out of scope

Editing this repository's profile, a lint command per card, running the linter on the builder's behalf
inside its permissions, and any change to CI.
