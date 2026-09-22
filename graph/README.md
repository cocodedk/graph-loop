# graph — the adaptive agent loop

**Start with `BLUEPRINT.md`** — the design, the task contract and the order of a
task. `DIARY.md` is the story of how it was learned; the repository's
`CLAUDE.md` carries the rules.

One driver that works a backlog to done: it picks the next atomic task, has it
reviewed before and after it is built, proves every gate red first (a
no-files, non-live card skips the build, the diff review and red-first, and
ends on one gate call after its contract review), and stops when the goal
passes, when nothing can move, or when you say so.

    python3 graph/graph-goal.py init    --backlog "$GRAPH_REPO/vault" --source spec/brief.md
    python3 graph/graph-goal.py approve --revision 1
    python3 graph/graph-goal.py run
    python3 graph/graph-goal.py status
    python3 graph/graph-goal.py remember   # after a run: each card's memory, from the log
    python3 graph/graph-goal.py stop        # after the running tasks
    python3 graph/graph-goal.py stop --now  # kill the recorded groups, keep the worktrees

A builder that reports `BLOCKED` leaves a scrubbed report in
`<workspace>/issues/` when the driver stops.

Rules it enforces, each bought with a failure:

- The backlog is the only task source. The planner selects and may slice; it
  never invents a task.
- Up to three code cards build side by side; `--lanes` may lower that ceiling. A
  Jev decision (`model_router.py`, `docs/ROUTER.md`) picks the configured model
  and effort for each build and review from the resource belt it is actually
  offered — never a free-form name. Every first attempt runs at medium; a
  builder climbs to high only from a recorded medium build on this same
  contract that then failed its gate, never from a round counter alone. A
  refusal before reading skips the unavailable account or model and tries the
  next configured one; the default belt includes Opus and Sonnet
  (`resources.py`, `accounts.py`, `models.py`). A gate that fails twice the
  same way re-slices the task.
- Reviews are routed the same way, always independent of the builder's own
  family: no eligible reviewer left means no accepted review, never a
  self-review. A low or malformed decision, an unlisted choice, or the
  decision service being unavailable all fall back to the first eligible
  independent resource at medium effort — the same fallback `GRAPH_ROUTER=off`
  gives explicitly, offline. `review.py` walks the routed belt, Codex reviewers
  first (`gpt-6-astra`, then `gpt-5.6-sol`).
- `--lanes auto [--lanes-max N]` lets the machine decide instead: lanes in a
  turn are the smallest of the frontier's width, that ceiling, the keeper's
  three and what the machine will take. It starts at the ceiling when one is
  given, adds one lane per clean turn, halves and then holds still for two
  turns when swap grows by more than 500 MB inside a turn, when memory or cpu
  pressure rises more than 20 points over that turn's own baseline, or when a
  gate that PASSED takes more than 2.5 times its time alone. It adds a lane
  only on a turn it actually measured. It never raises: a fault, a corrupt
  state file included, returns the last safe value and says so in the log.
  Every decision is an event with its inputs, and what it learned is in the
  campaign directory, so a restart does not throw a cut away.
- Every gate is proved red for the expected reason before a builder starts, and
  no builder can write a gate or a task contract. A no-files, non-live card has
  no builder to protect: it skips red-first, the build and the diff review, and
  runs its one gate (credential-scrubbed, boxed when bubblewrap works) straight
  from the contract review to done or failed.
- One worktree per task; files outside the task's list are refused — and for a
  no-files, non-live card, which owns none, anything its gate writes at all: a
  gate that edits its checkout is not evidence.
- A live task (declared `gate_has_side_effects`) holds a lock: one at a time on
  the shared stack. A no-files evidence task also runs by itself, for a
  scheduling reason: with no files there is no edit for a lane to build, so its
  gate runs on its own, one at a time.
- A task marked `blocked_by_human` is never started.
- Accepted work goes to a campaign branch. Never main, never force.
- Once accepted, a task's goal, pass condition, gate and file grant cannot be
  changed by an automatic rewrite. Different work needs a separate task.
- A diff review can block only on a changed line or changed Git metadata, with
  a requirement and evidence. Unrelated observations are saved separately;
  they do not become instructions to expand the current task.
- An ordinary keep checks this task and completed tasks with overlapping file
  grants. Wider integration checks belong in an explicit task's gate. Include
  affected shared contracts in the grant; unrelated recent tasks are not added.
- A failure in another task's combined check is compared in full with the
  candidate's recorded parent. Matching failure evidence goes to the earlier task; different evidence
  remains a possible regression. Missing evidence retries the check within the
  existing limit and preserves the finished work. Matching output cannot prove
  that a check which stops at its first failure has no hidden failures.

`remember` is the only command that writes outside the cards, and it is not on the loop's
path: run by hand after a driver stops, it projects the campaign log onto each card's
memory relative in `<Molecule>/relatives/`. It points at the log's numbered artifacts and
never copies them, it never touches a card, and a second run on the same log writes
nothing. A note is its own, whole, or not at all: it carries a digest of its own body, and
a file edited by hand in any way is kept exactly as it is and reported. Nothing is written
outside the vault or through a symlink. See `docs/RELATIVES.md`.

Keep machinery repairs and simulation feature work in separate task contracts.
A small fixture delivery proves the loop's controls; live mitigation still needs
its own recorded end-to-end evidence.
