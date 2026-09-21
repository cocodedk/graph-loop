---
source:
- docs/rfc/jev-cuts-brief.md:43
- docs/rfc/jev-cuts-brief.md:53
files:
- slicer/cut_verdicts.py
- slicer/tests/test_cut_verdicts.py
status: done
expect_red: the verdict was matched by substring
requirement:
  goal: 'slicer/cut_verdicts.py reads the atom names out of a verdict id by taking the id apart the way
    cut_questions built it: among atoms `a`, `ab` and `c`, a usable keep_together on the cut between `ab`
    and `c` merges that pair and no other, and among atoms `a` and `atom`, a usable fail on the atom id
    `atom:a` names `a`.'
  done_when: The gate passes. For atoms `a`, `ab` and `c` that all grant one shared file, a single usable
    keep_together verdict whose id is `cut_questions._cut_id("ab", "c")` gives `merges` exactly `[("ab",
    "c")]`. For atoms `a` and `atom`, a usable fail whose id is `atom:a` gives `findings` exactly `["Atom
    a fails the question one_job."]`. slicer/tests/test_cut_check.py stays green.
  sources:
  - docs/rfc/jev-cuts-brief.md:43
  - docs/rfc/jev-cuts-brief.md:53
contract_seen: 9fedd6f841db9aa5
accepted_criteria:
  goal: 'slicer/cut_verdicts.py reads the atom names out of a verdict id by taking the id apart the way
    cut_questions built it: among atoms `a`, `ab` and `c`, a usable keep_together on the cut between `ab`
    and `c` merges that pair and no other, and among atoms `a` and `atom`, a usable fail on the atom id
    `atom:a` names `a`.'
  gate: "set -e -o pipefail\ntimeout 600 python3 - <<'PY'\nimport os, pathlib, sys, types\nroot = pathlib.Path(os.getcwd()).resolve()\n\
    sys.path.insert(0, str(root / \"graph\" / \"lib\"))\nsys.path.insert(0, str(root / \"slicer\"))\n\
    import cut_verdicts\nfrom cut_questions import _cut_id\n\ndef atom(name, stage, files):\n    return\
    \ {\"name\": name, \"stage\": stage, \"goal\": f\"goal {name}\", \"files\": files,\n            \"\
    gate\": \"g\", \"done_when\": f\"done {name}\"}\n\ndef verdicts(ident, question, choice, confidence=0.9):\n\
    \    asked = types.SimpleNamespace(id=ident, questions={question: {}})\n    reply = types.SimpleNamespace(ok=True,\
    \ answers={\n        question: {\"choice\": choice, \"confidence\": confidence}})\n    return cut_verdicts.read(asked,\
    \ reply)\n\ncuts = {\"atoms\": [atom(\"a\", 1, [\"s.py\"]), atom(\"ab\", 2, [\"s.py\"]), atom(\"c\"\
    , 3, [\"s.py\"])]}\nonly = verdicts(_cut_id(\"ab\", \"c\"), \"cut\", \"keep_together\")\npaired =\
    \ cut_verdicts.merges(cuts, only)\nassert paired == [(\"ab\", \"c\")], f\"the verdict was matched\
    \ by substring: {paired}\"\n\nnamed = {\"atoms\": [atom(\"a\", 1, [\"x.py\"]), atom(\"atom\", 2, [\"\
    y.py\"])]}\none = verdicts(\"atom:a\", \"one_job\", \"fail\")\nraised = cut_verdicts.findings(named,\
    \ one)\nassert raised == [\"Atom a fails the question one_job.\"], \\\n    f\"the verdict was matched\
    \ by substring: {raised}\"\nprint(\"PROBE OK\")\nPY\n(cd slicer/tests && timeout 600 python3 -m unittest\
    \ test_cut_check)"
  done_when: The gate passes. For atoms `a`, `ab` and `c` that all grant one shared file, a single usable
    keep_together verdict whose id is `cut_questions._cut_id("ab", "c")` gives `merges` exactly `[("ab",
    "c")]`. For atoms `a` and `atom`, a usable fail whose id is `atom:a` gives `findings` exactly `["Atom
    a fails the question one_job."]`. slicer/tests/test_cut_check.py stays green.
  files:
  - slicer/cut_verdicts.py
  - slicer/tests/test_cut_verdicts.py
rebuild_from: /var/tmp/graph-trees/graph-cr_6vjmh/task-cut-verdict-ids-are-parsed
session: 0fc0de70-3c07-4aa3-bdb5-52ba3b15a477
session_account: personal

commit: 4f6c9e2b55cc3167140bc77a402041f61ee94545
worktree: /var/tmp/graph-trees/graph-cr_6vjmh/task-cut-verdict-ids-are-parsed
kept_at: '2026-09-20T17:56:24Z'
---

## Goal

slicer/cut_verdicts.py reads the atom names out of a verdict id by taking the id apart the way cut_questions built it: among atoms `a`, `ab` and `c`, a usable keep_together on the cut between `ab` and `c` merges that pair and no other, and among atoms `a` and `atom`, a usable fail on the atom id `atom:a` names `a`.

## Why

The brief says `merges` returns a pair only for the cut the verdict answered, and `findings` one sentence per usable fail naming that atom. Matching by substring makes one confident verdict merge a pair nobody asked about whenever an atom name is a prefix of another, which is how a molecule loses an atom to a verdict that was never about it.

## Done when

The gate passes. For atoms `a`, `ab` and `c` that all grant one shared file, a single usable keep_together verdict whose id is `cut_questions._cut_id("ab", "c")` gives `merges` exactly `[("ab", "c")]`. For atoms `a` and `atom`, a usable fail whose id is `atom:a` gives `findings` exactly `["Atom a fails the question one_job."]`. slicer/tests/test_cut_check.py stays green.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, sys, types
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
sys.path.insert(0, str(root / "slicer"))
import cut_verdicts
from cut_questions import _cut_id

def atom(name, stage, files):
    return {"name": name, "stage": stage, "goal": f"goal {name}", "files": files,
            "gate": "g", "done_when": f"done {name}"}

def verdicts(ident, question, choice, confidence=0.9):
    asked = types.SimpleNamespace(id=ident, questions={question: {}})
    reply = types.SimpleNamespace(ok=True, answers={
        question: {"choice": choice, "confidence": confidence}})
    return cut_verdicts.read(asked, reply)

cuts = {"atoms": [atom("a", 1, ["s.py"]), atom("ab", 2, ["s.py"]), atom("c", 3, ["s.py"])]}
only = verdicts(_cut_id("ab", "c"), "cut", "keep_together")
paired = cut_verdicts.merges(cuts, only)
assert paired == [("ab", "c")], f"the verdict was matched by substring: {paired}"

named = {"atoms": [atom("a", 1, ["x.py"]), atom("atom", 2, ["y.py"])]}
one = verdicts("atom:a", "one_job", "fail")
raised = cut_verdicts.findings(named, one)
assert raised == ["Atom a fails the question one_job."], \
    f"the verdict was matched by substring: {raised}"
print("PROBE OK")
PY
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_check)
```

## Note

Red today: the probe fails with `the verdict was matched by substring: [('a', 'ab'), ('ab', 'c')]`, because slicer/cut_verdicts.py:60 tests `one in i and two in i`. slicer/tests/test_cut_verdicts.py is in the file list because its verdict ids (`alpha|beta`) are not ids `cut_questions` ever builds; the gate does not run it. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
