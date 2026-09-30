# 14: the waiting mark survives a reset of the spec folder

## What the owner wants

The dashboard's waiting marks (`? awaiting answer`, `✖ stopped`, `● pr open`) and its `waiting for you:`
block come from `lean_status` in the spec's front matter, which the loop writes as an uncommitted edit of
the project's own checkout. Any `git checkout -- docs/lean`, `git stash` or branch switch wipes it, and a
project that waits for a person drops off the screen, although the loop's own event log still says exactly
what happened. This is issue #234, graded `P2`; the owner asked on 30 September 2026 that the loop build it.

## What changes

- **`lean_grilled` names what it grilled.** The event gains `specs`: the list of slugs of the spec files the
  grill read (as the dashboard slugs a spec file name). Today it names none, so a question cannot be tied
  to a spec from the log. Every other field of the event stays.
- **The mark falls back to the log.** `status_of` (or the mark rule in `graph/lib/project_specs.py`) reads,
  for a spec whose front matter holds **no** `lean_status`, the project's event log
  `<project>/scratchpad/lean/events*.jsonl` (the files the dashboard already reads for costs, in order).
  The newest event that names the spec decides:
  - `lean_grilled` whose `specs` holds it and whose `questions` is not empty → `questions`;
  - `lean_stopped` with `task` equal to its slug → `stopped`;
  - `lean_published` with `task` equal to its slug → `pr_open`;
  - a newer `lean_feature_started` for it, or a `lean_grilled` for it with empty `questions` → no status
    (waiting).
  An event older than a newer one for the same spec never decides; an unreadable line is skipped.
- **Everything else stays as it is.** A front matter `lean_status` still wins over the log; `building` and
  `built` still win over any status; a spec that no event names stays `waiting`; the loop's own writing of
  the front matter is unchanged.

## Edges

- A project with no event log, or an unreadable one, behaves exactly as today.
- Log lines without a slug the spec can match are ignored; slugs are compared as the dashboard slugs names.
- The list's `waiting for you:` block and the project view use the same mark, so both recover.
- Reading the log writes nothing and starts nothing.
- Every Python file stays at or under 200 lines; `graph/lean_run.py` stands near 200, so the one added field
  is a few characters in the existing `ws.event("lean_grilled", ...)` call.

## Done when

The driver's and the slicer's tests pass, and new tests prove (a temp project with a fake event log; no real
loop):

1. The `lean_grilled` event carries `specs` with the slugs of the specs grilled, and keeps its other fields.
2. A spec whose front matter has no status but whose newest event is a grill with questions is marked
   `? awaiting answer`; a stop gives `✖ stopped`; a publish gives `● pr open`.
3. A newer `lean_feature_started`, or a newer grill with no questions, clears it to waiting.
4. A front matter `lean_status` wins over the log; built and building win over both.
5. A spec named by no event, a project with no log and a log with broken lines all behave as today.
6. The list's `waiting for you:` block shows a spec whose front matter was wiped and whose log says it
   waits.
7. Every earlier test still passes. The builder may change any earlier test that pins the exact fields of
   the `lean_grilled` event, and nothing else in them. The builder adds new test files as the checks above
   need.

## Out of scope

Committing the front matter, a status file in the workspace, reading a workspace other than
`<project>/scratchpad/lean`, and any change to when the loop stops or restarts.
