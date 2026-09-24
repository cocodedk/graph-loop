# Grilling stage — the names and shapes a card may rely on

The specifications under `vault/specs` say what the stage must do and deliberately name no
file, module or format. A gate cannot be written against nothing, so this note **grants**
them. A card may add private helpers; it may not rename or reshape what is granted here.
Where this note and a confirmed decision (`grilling-stage-decisions.md`) disagree, the
decision wins and this note is wrong.

House rules apply: Python, PyYAML the only runtime dependency, every file under 200 lines,
no new `GRAPH_*` environment name — everything is a command-line argument.

Before grilling starts, the campaign must have a proven `contact` record, written by
`graph-goal.py --workspace <campaign> contact "<email-address>"` after a successful
email. Refuse a workspace without it; use `Workspace.require_contact()` at entry.

## Where the code lives

A new top-level package `grill/`, beside `graph/` and `slicer/`, with its tests in
`grill/tests/`. A gate has the shape
`(cd grill/tests && timeout 600 python3 -m unittest <module>)`.

| Module | One job | Granted entry points |
|---|---|---|
| `grill/record.py` | the decision record (D5) | `load(session)`, `resolve(record, question, kind, text, turn)`, `supersede(record, question, by_turn)`, `pending(record)`, `current(record)` |
| `grill/session_log.py` | the session record, append-only | `append(session, row)`, `rows(session)`, `resume_point(session)` |
| `grill/questions.py` | the prepared question set | `load(session)`, `eligible(analysis, record)`, `save(session, analysis)` |
| `grill/select.py` | choosing the next question (D1) | `next_question(analysis, record, after, chooser, state)` → `Selection(question, chosen_by, request)`, `chosen_by` one of `rule`, `order`, `chooser` |
| `grill/interpret.py` | reading a free-text answer | `Interpretation(alternative, kind, confidence, by)`; `interpret(ask, question, exact, alternatives, decisions, evidence)` |
| `grill/route.py` | one turn under D3's states, counted as D6 says | `turn(session, answer, models, states)` → `TurnResult(resolved, counts, rows)` |
| `grill/states.py` | the state switches (D2, D3) | `load(session)`, `switch(session, what, to, by, report=None)` |
| `grill/brief.py` | composing, readiness, confirmation | `compose(session)`, `ready(session)`, `confirm(session, revision, by)` |
| `grill/fidelity.py` | the five kinds of blocking finding | `check(brief_text, record)` → `[Finding(kind, decision, consequence)]` |
| `grill/late.py` | a question found by a later stage | `record_question(session, wording, affected_work)`, `open_questions(session)` |
| `grill/evaluate.py` | replay, measures, the report | `replay(recorded, models)`, `report(sessions, annotations)` |
| `grill/grill.py` | the command | `analyse`, `ask`, `brief`, `confirm`, `switch`, `late-question`, `evaluate`; every one takes `--session DIR` |

**Models are injected, never imported.** Every function that needs a model takes a callable:
`ask_text(prompt) -> str` and `ask_decisions(state, questions) -> dict`. Tests pass scripted
callables and a scripted user (a list of answers); no test touches the network. Production
wiring lives in one place, `grill/models.py`, which reaches the text model through
`graph/lib/providers` and the decisions model through the transport `graph/lib/provider_jev.py`
holds — factored out only if triage's contract and tests stay exactly as they are. The
decisions model is a seam: `models.py` is the only file that knows which one is used.

## The session directory

Everything the stage remembers is in the directory given as `--session`. YAML files are
rewritten whole through a sibling temporary file; the log is only ever appended to.

**`analysis.yaml`** — the question set.
`completed: true|false`; `questions:` a list, each
`{id, wording, consequence, evidence: [..], choices: [{id, text}], prerequisites: [id],
follow_ups: [{when: <choice id>, ask: <question id>}], order: {position, reason},
in_scope: true|false}`. `completed: false` means no question may be asked from it.

**`decisions.yaml`** — the decision record. `questions:` a map from question id to
`{state: pending|resolved, decision: {kind: answer|delegation|exclusion, text, turn, at} | null,
superseded: [{kind, text, turn, at, superseded_by_turn}]}`. `current(record)` is the map of
resolved decisions; a superseded entry is never in it.

**`session.jsonl`** — the session record, one JSON object per line, each with `turn`, `at`
and `kind`. Kinds: `analysis`, `asked` (`question`, `chosen_by`), `answer` (`question`,
`exact`, `picked`), `interpretation` (`by: text|decisions`, `alternative`, `answer_kind`,
`confidence`, `acted`), `request` (`purpose: text|interpret|select`,
`outcome: ok|invalid|unavailable|timeout`, `seconds`, `cost`), `resolved`, `pending`,
`superseded`, `contradiction_shown`, `late_question` (`wording`, `affected_work`),
`completeness_review`, `review_finding`, `confirmed`. D6's three counts are the number of
`request` rows of each `purpose` in a turn — every request made, whatever its outcome.
`answer_kind` is one of `answers`, `answers_part`, `may_contradict`, `new_requirement`,
`unclear`.

**`states.yaml`** — `interpret: {state: off|observe|act, act_kinds: [answer_kind]}`,
`choose: {state: off|observe|act}`, `history: [{what, to, by, at, report}]`. Absent file
means everything `off`. `switch` to `act` without a `report` naming a reviewed example of
that category is refused and changes nothing.

**`brief.md`** — the agreed brief: front matter `{revision, request, confirmed: {by, at} | null}`,
then `## Outcome`, `## Scope`, `## Decisions` with one `### <question id>` per current
decision, `## Examples`, `## Constraints`, `## Exclusions`, `## Delegated choices`. Any
change to the body makes a new `revision` and clears `confirmed`.

**`annotations.yaml`** — a reviewer's verdicts on a recorded session, a list keyed by
`turn`: `{turn, reviewed_alternative, reviewed_kind, unnecessary_question, wrongly_answered,
contradiction_missed, brief_lost_or_altered: [question id], reviewer_gaps: [text]}`. A turn
with no entry is *not annotated*.

**`report.yaml`** — the evaluation report: `sessions`, `categories:` a map from each
`answer_kind` and `choose` to `{reviewed, disagreed: [session/turn], unannotated}`,
`mechanical: {wait_seconds: {median, slowest}, cost, repeated_questions}`, `judgment:` each
measure a number or the string `not annotated`, `calls_avoided:` a number or `no baseline`.

## Handing the brief on

`slicer/branches.py` and `slicer/speccer.py` each gain `--brief-file PATH` and
`--brief-revision N`. With them, the confirmed brief's text and revision are put into the
writer's and the reviewer's prompt as their own block; without them both behave exactly as
they do today. A brief whose front matter shows no confirmation of that revision is refused.
