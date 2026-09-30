# 07: gpt-6-sol is replaced by gpt-6.1-sol

## What the owner wants

Wherever graph-loop uses `gpt-6-sol`, it uses `gpt-6.1-sol` instead: the owner said on 30 September 2026
that it is cheaper and better, and that any other use of `gpt-6-sol` must be replaced. That is the grill
(the reviewer that reads a spec before anything is built) and the review of a finished diff, both at the
effort they have today (`xhigh`). Nothing else changes: no new setting, no second model list, no new belt.

## What changes

- **The code names the model in one place.** `graph/lib/models.py`'s `_REVIEWERS` becomes
  `("gpt-6.1-sol",)`, and `providers.REVIEW_MODEL` is that same model, read from `models.reviewers()`
  rather than typed a second time, so exactly one line of code names it. The grill's and the review's
  `lean_call_started` events (which carry `model`) then say `gpt-6.1-sol`, and so does the dashboard's
  loop line.
- **The words follow.** Every docstring, comment and README line that says the reviewer or the grill is
  `gpt-6-sol` says `gpt-6.1-sol`, in `graph/lib/models.py`, `graph/lib/providers.py`,
  `graph/lib/resources.py`, `graph/lib/review.py` and `graph/README.md`. A comment that records what
  the owner decided on an earlier date keeps its date and its old model name, since it is history; the
  current choice gets its own dated line beside it.
- **The tests follow.** A test that pins `gpt-6-sol` as the model in force expects `gpt-6.1-sol`; a test
  that only uses the name as sample text is left alone.

## Edges

- The review belt still ends with the claude reviewers, so a model at capacity or refused falls through
  exactly as today.
- `gpt-6-astra` and any model named in a dated historical comment stay as they are.
- Every Python file stays at or under 200 lines (`graph/lib/providers.py` stands at exactly 200: keep it
  there or move code out and keep the names importable).

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. `models.reviewers()` is `["gpt-6.1-sol"]` and `providers.REVIEW_MODEL` equals its first entry.
2. The grill's and the review's `lean_call_started` events name `gpt-6.1-sol` and effort `xhigh`.
3. No tracked file outside a dated historical comment and this spec names `gpt-6-sol` (a test reads
   `git ls-files` and checks each hit is such a comment).
4. Every earlier test still passes. The builder may change any earlier test that pins `gpt-6-sol`, and
   nothing else in them. The builder adds new test files as the checks above need.

## Out of scope

The builder's model, effort settings, cost limits, and a setting to choose a model.
