---
lean_status: questions
lean_rounds: 1
lean_asked: Should GRAPH_REVIEWERS replace the block’s default reviewer list, as it does today, or append
  to it, as the spec also requires?
---
# 07: one block names every lean model and effort, and the grill and review run on gpt-6.1-sol

## What the owner wants

Changing which model or effort a lean call uses is one line in one place. Today the reviewer's model is in
`graph/lib/models.py` and typed again in `graph/lib/providers.py`, the builder's model is in
`providers.py`, and the efforts sit in `graph/lean_run.py` and `providers.py`. The owner said on 30
September 2026 that `gpt-6.1-sol` is cheaper and better than `gpt-6-sol`, and that every use of
`gpt-6-sol` must be replaced by it. With the block, that is a one-line edit.

## The block

`graph/lib/models.py` gains one block of data, named `LEAN`, near the top, with the model and the effort of
each lean call and a one-line comment saying it is the place to change them:

| Call | Model | Effort |
|---|---|---|
| builder (the first build) | `claude-sonnet-5-5` | `high` |
| repair (each repair round) | `claude-sonnet-5-5` | `high` |
| grill | `gpt-6.1-sol` | `xhigh` |
| review | `gpt-6.1-sol` | `xhigh` |

The values are today's, except the grill's and the review's model, which is `gpt-6.1-sol` instead of
`gpt-6-sol`. The shape (a dict of dicts, a small dataclass) is the builder's choice, as long as it is
plain data at the top of the file.

## What reads it

- `providers.MODEL`, `providers.REVIEW_MODEL` and `providers.REVIEW_EFFORT`, and `lean_run`'s
  `BUILD_EFFORT` and `REPAIR_EFFORT`, take their values from the block instead of typing them, so no
  line of code outside the block names a lean model or effort.
- `models.reviewers()` (the codex reviewer list) is the review's model from the block alone
  (`["gpt-6.1-sol"]`), and `GRAPH_REVIEWERS` **replaces** that list when it is set, exactly as it does
  today: it never appends. The environment overrides `GRAPH_BUILDERS`, `GRAPH_REVIEWERS` and
  `GRAPH_CLAUDE_REVIEWERS` keep working exactly as they do.
- The `lean_call_started` events of the build, the repair, the grill and the review carry the block's
  model and effort, so the dashboard shows `gpt-6.1-sol xhigh` on a grilling or reviewing line.
- The campaign router's rung ladders and the other belts (planners, claude reviewers) do not move.

## The words follow

Every docstring, comment and README line that says the reviewer or the grill is `gpt-6-sol` says
`gpt-6.1-sol`, in `graph/lib/models.py`, `graph/lib/providers.py`, `graph/lib/resources.py`,
`graph/lib/review.py` and `graph/README.md`. A comment that records what the owner decided on an earlier
date keeps its date and old model name, since it is history; the current choice gets its own dated line
beside it. A test that pins `gpt-6-sol` as the model in force expects `gpt-6.1-sol`.

## Edges

- The review belt still ends with the claude reviewers, so a model at capacity or refused falls through as
  today.
- `gpt-6-astra` and any model named in a dated historical comment stay as they are.
- Every Python file stays at or under 200 lines; `graph/lib/providers.py` stands at exactly 200 and
  `graph/lean_run.py` at 199: moving values out should shorten them, and every name a test patches stays
  importable from where it is.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. The block holds the four calls with the values above, and `models.reviewers()` starts with the block's
   review model.
2. Patching the block (a test changes one model and one effort) changes the model and effort the build,
   the repair, the grill and the review are called with, and the model and effort their
   `lean_call_started` events carry (fake the calls; no real model).
3. No tracked Python file outside the block names `gpt-6.1-sol`, `claude-sonnet-5-5` as a lean model, or a
   lean effort as a literal (a test reads the files and lists any hit), and no tracked file outside a
   dated historical comment and this spec names `gpt-6-sol`.
4. `GRAPH_REVIEWERS` still overrides the reviewer list.
5. Every earlier test still passes. The builder may change any earlier test that pins a lean model or
   effort, and nothing else in them. The builder adds new test files as the checks above need.

## Out of scope

The campaign router's ladders, the planner and claude-reviewer belts, a file format or a new setting,
cost limits, and any change to what the dashboard shows beyond the values it already reads from events.
