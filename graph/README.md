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
    python3 graph/graph-goal.py stop        # after the running tasks
    python3 graph/graph-goal.py stop --now  # kill the recorded groups, keep the worktrees

Rules it enforces, each bought with a failure:

- The backlog is the only task source. The planner selects and may slice; it
  never invents a task.
- Up to three code cards build side by side; `--lanes` may lower that ceiling,
  never raise it — three is the keeper's own limit, because it gives up after
  three rebuilds of a branch that moved under it. The first choice for a build
  is `claude-opus-5` on the work account or the
  personal one (cap), at effort high climbing to xhigh as the task's weight or a
  lost round demands — never below high, never above xhigh (`effort.py`). A refusal
  before reading skips the unavailable account or model and tries the next
  configured pair; the default belt includes Opus and Sonnet (`resources.py`,
  `accounts.py`, `models.py`). A gate that fails twice the same way re-slices the
  task.
- `--lanes auto [--lanes-max N]` lets the machine decide instead: lanes in a
  turn are the smallest of the frontier's width, that ceiling, the keeper's
  three and what the machine will take. It starts at the ceiling when one is
  given, adds one lane per clean turn, halves and then holds still for two
  turns when swap grows by more than 500 MB inside a turn, when memory or cpu
  pressure rises more than 20 points over that turn's own baseline, or when a
  gate takes more than 2.5 times its time alone. It never raises: a fault
  returns the last safe value and says so in the log. Every decision is an
  event with its inputs.
- The frontier is visible. `plan` and `status` print the waves the backlog would
  run in — what could start together, then what that releases — labelled as of
  that moment, because the next plan phase re-slices it. A held card is listed
  as held and never scheduled. A wave that costs more than one turn says so in
  the same line: how wide, the cap, how many turns — one turn each for the
  cards that run alone, the rest packed into lanes. Each turn records that
  width, the cap and the lanes it ran, and `report` names the turns where the
  graph was wider than the loop.
- Reviews try a fresh `codex exec --model gpt-6-astra` first (gpt-5.6-sol behind it), once on the task
  contract before any edit and once on the diff, at effort medium climbing to
  high for a heavier task or a round that already failed — never below medium,
  never above high (`effort.py`); only when Codex refuses before reading does a
  read-only Claude review follow (`review.py`).
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

Keep machinery repairs and simulation feature work in separate task contracts.
A small fixture delivery proves the loop's controls; live mitigation still needs
its own recorded end-to-end evidence.
