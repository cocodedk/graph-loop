# 07: the grill runs on gpt-6.1-sol

## What the owner wants

The grill, the reviewer that reads a spec before anything is built, runs on `gpt-6.1-sol` at `xhigh`:
the owner said on 30 September 2026 that it is cheaper and better than `gpt-6-sol`. The review of a
finished diff stays on `gpt-6-sol` at `xhigh`, and everything else stays as it is.

## What changes

- **The grill has its own list of models.** `graph/lib/models.py` gains `grillers()`: `gpt-6.1-sol`
  first, then the models `reviewers()` names, in its order, so the grill never runs on fewer models than
  the review does.
- **The grill has its own belt.** `resources.belt("grill")` is the codex resources for `grillers()` in
  order, then the claude resources of the review belt, exactly as `belt("review")` builds its tail.
  `belt("review")` and `belt("decide")` do not change.
- **The grill uses it.** The grill in `graph/lean_run.py` passes `belt("grill")` to `review.codex`, so a
  refusal or a model at capacity falls to the next model as a review does; its effort stays `xhigh`.
- **The event tells the truth.** The grill's `lean_call_started` event carries `model` `gpt-6.1-sol`
  (the first model of its belt) instead of the reviewer's, so the dashboard's loop line shows it.

## Edges

- When `gpt-6.1-sol` is not available on a machine, or refuses, the grill goes on with the next model of
  its belt; nothing new is asked of the person and no new setting exists.
- `graph/lean_run.py` stands at 199 lines and no Python file may pass 200: move code to a module, and keep
  every name a test patches importable from `lean_run` (`build`, `judge`, `grill`, `masked`).

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. `models.grillers()` starts with `gpt-6.1-sol` and continues with `models.reviewers()` in order;
   `models.reviewers()` is unchanged.
2. `resources.belt("grill")` is the codex resources for `grillers()` in order, then the claude resources
   of `belt("review")`; `belt("review")` and `belt("decide")` are unchanged.
3. The grill passes the grill belt to the codex call, and a first model that refuses lets the second
   answer (fake the call; no real model).
4. The grill's `lean_call_started` event names `gpt-6.1-sol` and effort `xhigh`; the review's event still
   names `gpt-6-sol`.
5. Every earlier test still passes. The builder may change any earlier test whose expectation this spec
   changes (a test that pins the grill's model or belt), and nothing else in them. The builder adds new
   test files as the checks above need.

## Out of scope

The review of a diff, the builder, effort settings, cost limits, and a setting to choose the grill's
model.
