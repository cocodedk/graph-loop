# Brief — a decisions model judges every cut before the paid review

This brief and the files it names are the only authority for this campaign. It grants
nothing it does not state.

## Goal

Whenever the slicer proposes a molecule — for a gap in the sources or for a card that hit a
wall — a decisions model judges each cut between its atoms and each atom's quality in
seconds, **before** the independent review is paid for; its verdicts are recorded, and,
when a person has switched it to act, they merge what belongs together and send findings
into the planner's repair round. It never accepts or refuses a molecule by itself.

## Why

Reviews are most of a campaign's clock, and the slicer pays a full review per molecule.
Measured on a real backlog: 69 atoms and 32 cuts judged in 7 seconds for cents, the
confident "keep together" verdicts right, one confident verdict in thirty wrong, and no
opinion at all on a gate that could never pass — so the model routes, and review decides.

## Facts this brief grants

- Python 3, PyYAML the only runtime dependency, every file under 200 lines, one job per
  module stated in its first docstring line, no new `GRAPH_*` environment name, nothing
  local in a tracked file (`scripts/scrub-check.sh` must pass), `ruff check .` clean.
- A gate has the shape `(cd slicer/tests && timeout 600 python3 -m unittest <module>)` or
  the same under `graph/tests`. No gate may touch the network: the decisions model and the
  text model are always injected callables, and tests pass scripted ones.
- `graph/lib/provider_jev.py` and `graph/lib/triage_jev.py` keep their present behaviour,
  and their existing tests stay green unchanged. `provider_jev.ask(body, allowed)` is
  hardwired to triage's one question; this campaign adds a general door beside it and
  does not change that one.
- The slicer's closed answer, its validation and its review are described in
  `graph/SLICER.md` sections 5 and 6 and implemented in `slicer/slicer.py`,
  `slicer/slicer_answer.py`, `slicer/contracts.py` and `slicer/slicer_law.py`.

## Names and shapes this brief grants

| Module | One job | Entry points |
|---|---|---|
| `graph/lib/decisions.py` | ask a decisions model several typed questions about one state | `ask(state, questions, post=None) -> Answer(ok, answers, seconds, cost, why)`; `post` is the injected transport, defaulting to the one `provider_jev` uses; never raises |
| `slicer/cut_questions.py` | build the questions, pure | `for_cuts(molecule) -> [Asked(id, state, questions)]`, one per adjacent pair of atoms; `for_atoms(molecule, wall=None) -> [Asked]`, one per atom |
| `slicer/cut_verdicts.py` | read verdicts and say what follows, pure | `read(asked, answer, gate=0.6) -> Verdict(id, question, choice, confidence, usable)`; `merges(molecule, verdicts) -> [(atom, atom)]`; `findings(molecule, verdicts) -> [str]`; `apply_merges(molecule, pairs) -> molecule` |
| `slicer/cut_states.py` | the three states | `load(campaign) -> "off"|"observe"|"act"`; `switch(campaign, to, by)`; file `<campaign>/cut-states.yaml` with `state` and a `history` list of `{to, by, at}`; absent file means `off` |
| `slicer/cut_check.py` | run the check on one proposed molecule | `check(molecule, campaign, space, ask, wall=None) -> Checked(molecule, findings, verdicts)` |

Questions. For a cut: `cut`, a choice of `split`, `keep_together`, `insufficient_evidence`.
For an atom, each a choice of `pass`, `fail`, `insufficient_evidence`: `one_job`,
`claims_only_what_is_proved` (the atom's `done_when` claims only what its gate proves),
`files_sufficient`. The state given for a cut is the two atoms as the planner wrote them;
for an atom, the atom and, when there is one, the wall's recorded findings.

A verdict is *usable* only at or above the gate (0.6). `merges` returns a pair only when the
verdict is a usable `keep_together`, the two atoms are adjacent, and they share a file.
`apply_merges` joins the second atom into the first — files united, goals and done-whens
joined, both gates kept in order — and renumbers the stages. `findings` returns one sentence
per usable `fail`, naming the atom and the question.

## Behaviour

1. **off** — nothing is asked; the slicer behaves exactly as today.
2. **observe** — after validation and before the independent review, the check runs; every
   request and verdict is recorded as events and artifacts in the campaign's log, with
   timing and cost; the molecule goes on unchanged.
3. **act** — as observe, and then: `merges` are applied and the merged molecule is validated
   again by the existing validator; `findings` are handed to the planner through the
   existing two-round repair path, as the validator's findings are; the independent review
   then reads the molecule as it stands. A molecule is never published or refused on a
   verdict alone.
4. A decisions model that is unavailable, slow past 20 seconds, or answers something
   malformed changes nothing: the molecule goes to review as it is and the event says why.
5. `graph-goal.py cuts --state off|observe|act --by NAME` switches the state and
   `graph-goal.py cuts` prints it with its history. `report` gains one section: requests,
   seconds, usable verdicts, merges applied, findings raised.
6. Docs: `graph/SLICER.md` gains a short section, and `docs/STATUS.md` says what is measured
   and what is not.

## Not in this campaign

Choosing where to cut from alternatives the model is offered, planning several molecules
in one round, gate templates, and any check on specifications before slicing. They are
recorded as tasks in `docs/rfc/grilling-stage-decisions.md` and are not granted here.
