---
status: spec
---

## Goal

The planning layer keeps a log of every model call it makes, writer and reviewer alike, as task T1 of docs/rfc/grilling-stage-decisions.md requires and as docs/DESIGN.md already demands of the loop: everything it says, hears and measures is written to an append-only log. Today slicer/branches.py records nothing and has no campaign directory, and slicer/speccer.py records only its writer's prompt and answer, so a reviewer's refusal survives as one line on standard output.

The branch writer and the spec writer each accept a campaign directory. For every call, writer and reviewer alike, they record the prompt, the reply, the start and end time, any failure with its kind, and the cost where the provider reports it. They use the record and event machinery the driver and the slicer already have, not a new one. A refusal's findings are kept in full. The report command can say where planning's clock and money went, by layer and by call. A run without a campaign directory still works and says once that nothing is being logged.

## Acceptance

1. With a campaign directory given, one branch-writer run and one spec-writer run, each using controlled (scripted) model responses, leave records in that directory. Each writer call and each reviewer call has its own record holding the prompt, the reply, the start time and the end time.
2. A controlled call that fails leaves a record that names the kind of failure. A controlled call whose provider reports a cost leaves a record with that cost. A call whose provider reports no cost leaves a record with no cost value and no invented one.
3. A controlled reviewer refusal leaves a record holding the full findings text, character for character, not a shortened form.
4. The report command, run on that campaign directory, prints planning's time and money by layer and by call. Its totals equal the sums of the recorded start/end times and costs.
5. A run of either writer with no campaign directory finishes with the same outcome as before and prints one message, once, saying that nothing is being logged. It writes no log files.
6. With controlled responses, the prompt text sent to the model in each call is the same whether or not a campaign directory is given. The reply the writer or reviewer receives from the provider is the same whether or not it is logged. Logging changes neither.
7. No prompt is built by reading the log's files back. A test that removes or replaces the log files between calls shows the prompts sent are unchanged. The reviewer's findings still reach the writer on a retry through slicer/repair.py, in memory, as they do today.
8. Every file this work adds is 200 lines or fewer. No existing file is shorter than before. `ruff check .` passes, and `scripts/scrub-check.sh` passes.
9. The log is append-only: a second run into the same campaign directory adds records and removes none.

## Boundaries

- Not granted: a new record or event format, or a new logging library. Existing machinery is reused, and PyYAML stays the only runtime dependency.
- Not granted: reading the log back to build any prompt. The log machinery may read its own files only to append, number and rotate them.
- Not granted: changing any prompt or reply. What a retry already receives in memory through slicer/repair.py is unchanged.
- Not granted: shortening any existing file, or changing any document beyond describing this work.
- Not granted: changing the driver's own logging, the gate, or the reviewer's verdict rules.
- Not granted: any account name, home directory, machine path, foreign commit hash or task identifier in a tracked file, including tests and commit messages.
- Not granted: a new required method or option that the acceptance items above cannot observe.
