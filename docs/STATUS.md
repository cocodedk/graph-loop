# Status, and where to pick this up

Last updated 20 September 2026.

The runtime is here. This file says what is proven, what is not, and what is still owed.

## What is here

- `graph/` — the driver, the supervisor, the watcher and its stand-in, the dashboard.
- `slicer/` — the plan phase: a branch writer, a speccer and the slicer that writes every
  card, each with its own independent reviewer.
- `docs/` — the design, this file, and the diary of what each rule cost.
- `plugins/graph/` — the method as a Claude Code skill; useful without the driver.
- `scripts/scrub-check.sh` — nothing local travels, checked over contents, filenames and
  the whole history.
- `--lanes auto` is an option, off unless asked for: a throttler that reads
  `/proc` every two seconds and decides each turn's lanes from a rise over that
  turn's own baseline. Its numbers come from a ladder of one, two and three
  lanes measured on one real machine; the criterion that fired there was swap,
  at three lanes. It never raises into the loop — a corrupt state file included
  — it adds a lane only on a turn it actually measured, and what it learned
  survives the restarts the driver takes routinely. `--lanes N` is untouched.
- The frontier is visible: `plan` and `status` print the waves the backlog would run in,
  each turn records that width against its lane cap, and `report` names the turns where
  the graph was wider than the loop. The projection is a snapshot — the next plan phase
  re-slices the backlog — and it is labelled as one wherever it is printed.

Both suites run here: the slicer's 211 tests are green and the driver's suite is 1644
tests. Six of them need a machine this one is not — a non-root user, a sandbox that can
take a variable out of a gate's environment, and a real session launcher — so how many
pass is a fact about the machine, not about the loop. `ruff check .` is clean.

## What the move changed

The loop used to live inside the repository it built, and four places quietly relied on
that. Each is configuration now, and nothing else names a particular project:

| variable | what it names | default |
|---|---|---|
| `GRAPH_REPO` | the repository being built | the directory you run from |
| `GRAPH_CAMPAIGN` | where the campaign remembers | `$GRAPH_REPO/scratchpad/graph-campaigns/current` |
| `GRAPH_BACKLOG` | the vault of cards | `$GRAPH_REPO/vault` |
| `GRAPH_HELPER` | that repository's own command tool, for a live card | none, and a live card gets no helper grant |
| `GRAPH_PROVISION_COPY` | gitignored folders a checkout needs, copied in | none |
| `GRAPH_PROVISION_LINK` | folders a checkout needs, symlinked | none |
| `GRAPH_ACCOUNTS` | `name=configdir` pairs the belt walks | one account on the default configuration |
| `WATCHER_CONFIG_DIR` | the account the watcher session runs on | the default account |

Eleven checks stayed behind, because their input was another repository's own records: two
that graded that backlog card by card, one that counted 383 endings in its campaign log,
seven that repaired a snapshot of its backlog, and one that read a single card out of its
history. The rules they guarded travel; the data could not. `triage_repairs` keeps its
synthetic tests in `test_triage_repair_requeue`, `test_triage_repair_rounds` and
`test_activation_never_recomputes_a_repair`.

## What is not proven

`--lanes auto` has not driven a real campaign. The decision is measured and tested as a
table, the throttler is proved not to raise under injected faults, and it has been run
end to end against stubbed lanes — but no unattended campaign has used it, so what it
does to a real backlog over days is not known.

**No campaign has finished unattended.** Seven runs on the code that came here: the
seventh built all three of its buildable cards and parked none, and could not end — fixed
since, but not measured since. Until a campaign finishes on its own, the difference
between this and a tool in a shell loop is the person typing the loop.

Triage asks a decisions model before the text model when its table cannot name a cause.
That rung has never been reached in a live run — every ending so far was named by the
table — so its numbers are replays of recorded endings, not a measurement.

Automatic gate repair is off. TRIAGE still works out how to repair a mute gate and writes
that repair as a preview needing an approval; nothing writes that approval now, so a
standing preview stays unapplied and says so once on the board. No card is stranded by it.

## What is still owed

- The loop's status vocabulary is its own (`todo`, `sliced`, `rejected`, `needs_slice`, …)
  rather than the four agreed words, `sliced → implemented → verified → merged`.
- A card should park on its **first** failure. It cannot yet: one counter is incremented
  both when the work fails and when the machine fails, so setting the cap to one would
  throw away paid work on a usage limit. That needs two counters.
- `lib/triage_preview.py` is dead while gate repair is off.
- `graph/BLUEPRINT.md` has table cells a thousand characters long. It is the reference for
  every part and nobody can read it in that shape.

## The rules this repository bought

- **A document is not authority about the code.** The design shipped claiming the logic was
  generic; four places in the source said otherwise. A claim of genericness is a
  measurement, and the measurement is a grep of the source, spelled the way the source
  spells it.
- **Take the file list from the repository, not from a document.** A hand-written inventory
  drifts; `git ls-files` does not.
- **A new check is not trusted until the case it exists to catch has failed in front of
  you.** The guard here contained every literal it forbade and excluded itself to pass.
  Then it failed on its own pattern file. Then it caught a leak that had been committed and
  deleted, which a working-tree scan passes and a history scan does not.
- **A check that reads the machine is not a check on the code.** Four checks here read
  git's own wording for a refusal, which git 2.55 changed, and one needed the machine to
  carry a git identity. All five went red on a build runner, on no change at all. Assert
  the loop's own hook line, and make whatever a test needs inside the test.
- **Scrub before anything enters the index.** A clean final checkout does not clean a
  history, and the guard reads the history too.

## The notes that are not here

Some of this migration's detail names the work the loop came from — which repository,
which branch, which commit, and the literals the guard checks for. That is kept privately
and is deliberately absent here. Everything in it that can be said without naming anything
is already above.
