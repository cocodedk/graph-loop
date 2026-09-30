# 09: a revise round is reviewed like a first build

## What the owner wants

When a spec is rerun while its own pull request is open with unresolved review threads, the loop fixes
the threads on that pull request's branch, but `check()` in `graph/lean_run.py` returns as soon as the
suite passes (`if revising: return "", None`). The Codex reviewer is never asked, so the fix is judged
by the suite alone. That holds only when the threads came from a reviewer that reads later pushes (a bot
or a person on the pull request). When the threads were posted by hand as the review, nobody re-reads
the fix: the builder marks its own paper. This is issue #216, graded `P1`, and the owner asked on 30
September 2026 that the loop build it.

## What changes

- **A revise round is judged like a first build.** After the suite passes, `check()` runs `judge()` on the
  round's diff (the change this round made against the branch it started from, not against `main`) and
  logs a `lean_review` event for it, with the same fields a first build's carries. A first build does
  exactly what it does today.
- **The reviewer sees the threads.** For a revise round the prompt of `judge()` gains a section
  `## The review threads this round answers` holding the threads' text (the `revise` text `run_feature`
  already has, cut to its first 6000 characters when longer), and says the change must fix each one:
  a thread still open is a reason to refuse.
- **The same rounds and limits.** A refusal starts a repair round of the same kind a first build's refusal
  starts, and the repair limit stays two, counting this round. An accepted round pushes to the open pull
  request as today.
- **A refusal after the last repair still pushes**, and the reviewer's findings go in the pull request's
  description, appended below its existing text, as a first build's do; the branch is never left behind.
- **No flag and no skipped event.** A revise round is never skipped, so there is no option to turn the
  review off and no `lean_review_skipped` event.

## Answers to the grill

- **Rounds:** a revise run is one revise build plus up to two repair rounds, the same as a first build's
  initial build plus up to two repairs. "Counting this round" in the repair-limit line means each repair
  counts against the two; the revise build itself is not one of them.
- **"A thread still open"** means the thread's defect is still unfixed in the round's diff, as the reviewer
  judges it from the threads' text and the change. It is not GitHub's resolved mark: the reviewer runs
  before the push, when GitHub still shows every thread unresolved, and the loop does not read or set that
  mark.

## Edges

- A crashed or unreadable review is not an accept, exactly as in a first build.
- When the round's diff is empty, the existing "the builder changed nothing" answer stays first; the
  reviewer is asked only after the suite passes.
- `graph/lean_run.py` stands at 199 lines and no Python file may pass 200: move code to a module and keep
  every name a test patches (`build`, `judge`, `grill`, `masked`, `check`) importable from `lean_run`.
- The prompt text of a first build does not change by a character.

## Done when

The driver's and the slicer's tests pass, and new tests prove (fake the reviewer, the suite and git; no
real model):

1. A revise round whose suite passes asks the reviewer once, with the threads' text in the prompt under
   the heading above, and logs `lean_review`; a first build's prompt is byte for byte what it was.
2. A revise round the reviewer accepts pushes to the pull request as today, and its event carries the
   reviewer's outcome.
3. A revise round the reviewer refuses starts a repair round, at most two in all, and the last refusal
   still pushes with the findings appended to the pull request's description.
4. A threads text longer than 6000 characters is cut to 6000 in the prompt; a shorter one is whole.
5. A crashed review of a revise round is not an accept.
6. `lean_review_skipped` exists nowhere, and no setting turns the revise review off.
7. Every earlier test still passes. The builder may change any earlier test that pins a revise round
   returning without a review, and nothing else in them. The builder adds new test files as the checks
   above need.

## Out of scope

A flag or profile line to skip the review, the other open issues (#220, #223, #224), and any change to how
the threads are fetched.
