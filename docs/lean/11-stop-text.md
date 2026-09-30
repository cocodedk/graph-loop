# 11: a stop reason and a crash text keep their cause

## What the owner wants

When a lean run stops, the person and anything reading the log must see why. Today two cuts hide it.
`graph/lean_run.py` writes `lean_stopped` (and `lean_repair`) with `why=why[-2000:]`, the **last** 2000
characters. The real cause sits at the **start** of the text ("the repair changed nothing. The builder
said: …", then the gate output), so a long gate output pushes it out and the log shows only a red gate
tail. And `graph/lib/provider_codex.py` keeps `text=(done.stdout or blob).strip()[:500]` for a crashed
Codex call: with empty stdout that is the first 500 characters of stderr, the start-up banner, while the
error is on its last line. These are issues #223 and the second gap of #224, both graded `P2`; the owner
asked on 30 September 2026 that the loop build them.

## What changes

- **A reason keeps its start and its end.** A small helper (its own module or an existing one, the
  builder's choice) returns a reason whole when it is 2000 characters or shorter; when it is longer it
  returns its first 600 characters, one marker line `[... N characters left out ...]` with the exact N, and
  its last 1400 characters. `lean_stopped` and `lean_repair` use it for their `why`. The mail body, the
  kept worktree's note and everything else that holds the whole reason stay as they are.
- **A crash text keeps its error.** For a Codex call that exits non-zero, the outcome's `text` is the last 500
  characters of what it printed (its stdout when it has any, else stdout and stderr together, as today),
  preceded by the last line that starts with `Error` when that line is not already inside those 500
  characters, separated by a blank line. A call whose output is 500 characters or shorter keeps it whole, as
  today. Its `kind`, `raw` and every other field do not change.

## Edges

- Exactly 2000 characters is whole; 2001 is cut. The marker's N is the characters left out, so the pieces
  and N add up to the original length.
- An empty reason stays empty.
- The first build's behaviour, the review and the suite do not change.
- Every Python file stays at or under 200 lines; `graph/lean_run.py` stands at or near 200, so the helper
  goes in another module and `lean_run` only calls it.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. A reason of 2000 characters or fewer is returned unchanged; one of 2001 is cut to its first 600, the
   marker with the right N, and its last 1400.
2. `lean_stopped` and `lean_repair` carry the cut form of a long reason and the whole of a short one; the
   mail is still sent with the whole reason.
3. A crashed Codex call with a long stderr whose last line starts with `Error` yields a text that ends with
   that line's neighbourhood (the last 500 characters) and contains the error line; a banner-only start is
   no longer what the text shows.
4. A crashed call with short output keeps it whole; a successful call's text is unchanged.
5. Every earlier test still passes. The builder may change any earlier test that pins the last 2000
   characters or the first 500, and nothing else in them. The builder adds new test files as the checks
   above need.

## Out of scope

The large-diff review failure (the other part of #224), the dashboard showing the cause of a stop, and any
change to the mail.
