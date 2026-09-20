---
source:
- docs/rfc/jev-cuts-brief.md:42
- docs/rfc/jev-cuts-brief.md:50
files:
- slicer/cut_questions.py
- slicer/tests/test_cut_questions.py
- slicer/tests/test_slicer_main_cut_check.py
status: todo
gate_reviewed_first: true
expect_red: 'KeyError: ''id'''
---

## Goal

On a molecule that slicer/contracts.py validate() returned, slicer/cut_questions.py builds its questions without raising: the one cut Asked carries both atom names in its id, each atom Asked carries its own atom's name in its id, and the verdicts read from those Asked objects merge that pair and name that atom.

## Why

The brief grants for_cuts and for_atoms over a proposed molecule. validate() closes an atom's keys to name, stage, goal, files, gate, done_when and the optional flags, so no real atom has an `id`, and the cut check raises KeyError on every molecule the slicer proposes today.

## Done when

The gate passes. On a two-atom molecule built through validate() — atoms named alpha and beta, both granting app.py, neither carrying an `id` key — for_cuts gives one Asked whose id holds both names, for_atoms gives one Asked per atom whose id holds that atom's name, and nothing raises. A usable keep_together verdict read from that cut merges (alpha, beta), and a usable fail on beta's one_job gives exactly "Atom beta fails the question one_job.". slicer/tests/test_cut_check.py stays green.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, sys, tempfile, types
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
sys.path.insert(0, str(root / "slicer"))
import contracts, cut_questions, cut_verdicts

repo = pathlib.Path(tempfile.mkdtemp())
(repo / "specs").mkdir()
(repo / "specs" / "greeting.md").write_text("# Greeting\nA greeting is returned.\n", "utf-8")
(repo / "app.py").write_text("present = True\n", "utf-8")

def atom(name, stage):
    return {"name": name, "stage": stage, "goal": f"do {name}", "files": ["app.py"],
            "gate": "set -e -o pipefail\nfalse", "done_when": f"{name} is proved"}

answer = {"result": "MOLECULE", "reason": "one gap", "molecule": {
    "name": "greeting", "source": ["specs/greeting.md:2"], "goal": "return a greeting",
    "why": "the function is absent", "needs": [],
    "atoms": [atom("alpha", 1), atom("beta", 2)]}}
whole = contracts.validate(answer, repo=repo, sources=[repo / "specs"], rows=[], target=None)
mol = whole["molecule"]
assert all("id" not in a for a in mol["atoms"]), "a validated atom carries no id"

cuts = cut_questions.for_cuts(mol)
per_atom = cut_questions.for_atoms(mol)
assert len(cuts) == 1 and len(per_atom) == 2, (len(cuts), len(per_atom))
assert "alpha" in cuts[0].id and "beta" in cuts[0].id, f"the cut id names neither atom: {cuts[0].id}"
for asked, name in zip(per_atom, ("alpha", "beta")):
    assert name in asked.id, f"the atom id does not name its atom: {asked.id} {name}"

def reply(**given):
    return types.SimpleNamespace(ok=True, answers={
        q: {"choice": c, "confidence": p} for q, (c, p) in given.items()})

verdicts = cut_verdicts.read(cuts[0], reply(cut=("keep_together", 0.9)))
verdicts += cut_verdicts.read(per_atom[1], reply(one_job=("fail", 0.9),
                                                 claims_only_what_is_proved=("pass", 0.9),
                                                 files_sufficient=("pass", 0.9)))
paired = cut_verdicts.merges(mol, verdicts)
assert paired == [("alpha", "beta")], f"the verdict did not map back to its atoms: {paired}"
raised = cut_verdicts.findings(mol, verdicts)
assert raised == ["Atom beta fails the question one_job."], f"the finding names no atom: {raised}"
print("PROBE OK")
PY
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_check)
```

## Note

Red today: `KeyError: 'id'` at slicer/cut_questions.py:28, because `for_cuts` reads `first["id"]` and a validated atom has only `name`. slicer/tests/test_cut_questions.py and slicer/tests/test_slicer_main_cut_check.py are in the file list because their atoms carry an `id` key that `contracts.ATOM` does not allow and `validate()` never produces; the gate runs neither of them. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
