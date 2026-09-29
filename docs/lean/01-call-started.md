# 01: the loop says when a call starts

## What the owner wants

A dashboard that shows what each running lean loop is doing now. Today a step writes nothing to the
loop's log until it ends, so a grill that runs for half an hour looks like a loop that does nothing.
This first step only makes the loop write a line when a step starts. The dashboard comes later.

## Behaviour

- The lean loop writes one event, `lean_call_started`, to the workspace's event log immediately
  before each of its three model calls: the **grill** (`lean_run.grill`), the **builder**
  (`lean_run.build`, the first build and every repair) and the **reviewer** (`lean_run.judge`).
- The event carries `purpose` (`grill`, `build` or `review`), `task` (the same name the call's
  `attempt` event uses: `grill` for the grill, otherwise the feature's name) and `effort` (the effort
  the call is made at).
- It is an added line only. What each call returns, what is mailed, what the other events say and
  the order of the other events all stay exactly as they are. The event is written once per call, so
  a build with two repairs has three `lean_call_started` events with `purpose` `build`.
- A call that fails or crashes still has its `lean_call_started` event: it is written before the
  call, not after.

## Constraint

`graph/lean_run.py` is at the 200-line cap. Make room by moving a whole function that the new lines
do not touch (for example `pr_body`) to a new module, and keep it importable from `lean_run` under the
same name. The tests that patch `lean_run.build`, `lean_run.judge`, `lean_run.grill` and
`lean_run.masked` must keep working without a change, apart from what "Done when" says.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. Each of the three call sites writes its `lean_call_started` event before the model is called: the
   fake model in the test looks at the event log when it is called and finds the event there.
2. The event's `purpose`, `task` and `effort` for the grill, the first build, a repair build and the
   review.
3. A build with two repairs writes three `build` events, and a run that stops after a red suite
   writes no `review` event.
4. Every earlier test still passes. The builder may change an earlier test only where it asserts the
   exact list of event kinds a run writes, and only to add `lean_call_started`; nothing else in an
   earlier test changes. The builder adds new test files as the checks above need.

## Out of scope

The dashboard itself, the card loop, and any change to what the loop does or decides.
