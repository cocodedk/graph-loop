---
source:
- docs/rfc/stalls-brief.md:67
- docs/rfc/stalls-brief.md:68
files:
- graph/lib/doctor.py
- graph/lib/doctor_slices.py
may_add_files: true
status: done
expect_red: a sliced card nobody names is not reported
requirement:
  goal: '`doctor.diagnose` raises one complaint about a `sliced` card whose `Needs` is empty and that
    no card names in `sliced_from`, because nothing can ever settle it. Over a backlog holding that card,
    a `sliced` card with an empty `Needs` that one card does name, a `sliced` card whose own `Needs` holds
    its piece, and an ordinary `todo` card, exactly one complaint is about the first card and none is
    about any other card in that backlog.'
  done_when: 'The gate passes. Over a temporary backlog holding `P` (`sliced`, empty `Needs`, nobody names
    it), `Q` (`sliced`, empty `Needs`) with `Q.one` naming `Q` in `sliced_from`, `R` (`sliced`, `needs:
    [R.a]`) with `R.a` `done`, and `S` (`todo`), `doctor.diagnose` returns exactly one complaint whose
    `about` is `P`, and no complaint whose `about` is `Q`, `Q.one`, `R`, `R.a` or `S`. `graph/lib/doctor_slices.py`
    imports. graph/tests/test_doctor.py, graph/tests/test_doctor_salvage.py and graph/tests/test_doctor_starved.py
    stay green. The gate does not prove the wording of the complaint or of what to do about it, and it
    does not prove anything about `settled`.'
  sources:
  - docs/rfc/stalls-brief.md:67
  - docs/rfc/stalls-brief.md:68
contract_seen: d5b62850fa44b6a1
accepted_criteria:
  goal: '`doctor.diagnose` raises one complaint about a `sliced` card whose `Needs` is empty and that
    no card names in `sliced_from`, because nothing can ever settle it. Over a backlog holding that card,
    a `sliced` card with an empty `Needs` that one card does name, a `sliced` card whose own `Needs` holds
    its piece, and an ordinary `todo` card, exactly one complaint is about the first card and none is
    about any other card in that backlog.'
  gate: "set -e -o pipefail\ntimeout 600 python3 - <<'PY'\nimport os, pathlib, sys, tempfile\nroot = pathlib.Path(os.getcwd()).resolve()\n\
    sys.path.insert(0, str(root / \"graph\" / \"lib\"))\nimport yaml\ntry:\n    import doctor_slices \
    \ # noqa: F401\nexcept ImportError:\n    sys.exit(\"a sliced card nobody names is not reported: there\
    \ is no doctor_slices module\")\nfrom backlog import Backlog\nfrom doctor import diagnose\nfrom workspace\
    \ import Workspace\n\nRED = \"a sliced card nobody names is not reported\"\n\n\ndef card(task_id,\
    \ status=\"todo\", needs=(), **extra):\n    row = {\"id\": task_id, \"goal\": f\"do {task_id}\", \"\
    status\": status, \"needs\": list(needs),\n           \"files\": [], \"gate\": \"true\", \"done_when\"\
    : f\"{task_id} passes\"}\n    row.update(extra)\n    return row\n\n\ndef book(*rows):\n    path =\
    \ pathlib.Path(tempfile.mkdtemp()) / \"backlog.yaml\"\n    path.write_text(yaml.safe_dump({\"schema\"\
    : \"e2e-backlog.v1\", \"tasks\": list(rows)},\n                                   sort_keys=False))\n\
    \    return Backlog(path)\n\n\nhere = Workspace(tempfile.mkdtemp()).init(goal=\"a probe\", backlog=\"\
    b.yaml\")\nout = diagnose(book(\n    card(\"P\", \"sliced\"),                   # nothing to settle\
    \ it: the complaint\n    card(\"Q\", \"sliced\"), card(\"Q.one\", \"todo\", sliced_from=\"Q\"),  \
    \ # a card names it\n    card(\"R\", \"sliced\", [\"R.a\"]), card(\"R.a\", \"done\"),            \
    \ # its Needs holds it\n    card(\"S\"),\n), here)\nabout = [one.about for one in out]\nassert about.count(\"\
    P\") == 1, f\"{RED}: complaints about P: {about.count('P')} in {about}\"\nfor settling in (\"Q\",\
    \ \"Q.one\", \"R\", \"R.a\", \"S\"):\n    assert settling not in about, \\\n        f\"{RED}: {settling}\
    \ was reported too, and something can settle it: {about}\"\nprint(\"PROBE OK\")\nPY\n(cd graph/tests\
    \ && timeout 600 python3 -m unittest test_doctor)\n(cd graph/tests && timeout 600 python3 -m unittest\
    \ test_doctor_salvage)\n(cd graph/tests && timeout 600 python3 -m unittest test_doctor_starved)"
  done_when: 'The gate passes. Over a temporary backlog holding `P` (`sliced`, empty `Needs`, nobody names
    it), `Q` (`sliced`, empty `Needs`) with `Q.one` naming `Q` in `sliced_from`, `R` (`sliced`, `needs:
    [R.a]`) with `R.a` `done`, and `S` (`todo`), `doctor.diagnose` returns exactly one complaint whose
    `about` is `P`, and no complaint whose `about` is `Q`, `Q.one`, `R`, `R.a` or `S`. `graph/lib/doctor_slices.py`
    imports. graph/tests/test_doctor.py, graph/tests/test_doctor_salvage.py and graph/tests/test_doctor_starved.py
    stay green. The gate does not prove the wording of the complaint or of what to do about it, and it
    does not prove anything about `settled`.'
  files:
  - graph/lib/doctor.py
  - graph/lib/doctor_slices.py
rebuild_from: /var/tmp/graph-trees/graph-t8fab8u2/task-doctor-flags-a-sliced-card-nobody-names
session: e7db8e7c-3bb9-42d2-a0ba-79d02238a51c
session_account: personal

commit: e3452a453ffaa9efa3579cbbf3ddfe7f2d0d16c6
worktree: /var/tmp/graph-trees/graph-t8fab8u2/task-doctor-flags-a-sliced-card-nobody-names
kept_at: '2026-09-21T06:42:24Z'
---

## Goal

`doctor.diagnose` raises one complaint about a `sliced` card whose `Needs` is empty and that no card names in `sliced_from`, because nothing can ever settle it. Over a backlog holding that card, a `sliced` card with an empty `Needs` that one card does name, a `sliced` card whose own `Needs` holds its piece, and an ordinary `todo` card, exactly one complaint is about the first card and none is about any other card in that backlog.

## Why

`settled` finishes a `sliced` card on its pieces. A parent with no pieces from either source has nothing to finish it, so every card behind it waits for ever and the board calls the queue healthy — which is the one failure that looks exactly like health, the reason `doctor_starved` exists. The loop cannot repair it: writing the pieces is a person's decision, or a decision to set the card `done` or `dropped`. So it is named, with the thing to do about it, as every other complaint in this file is.

`doctor.diagnose` already derives the parents that a successor names — `parents` and `sliced` at graph/lib/doctor.py:170 — for the salvage check, so the reading this complaint needs is the one already there. graph/lib/doctor.py is 188 lines, so the check itself belongs in a new graph/lib/doctor_slices.py and `diagnose` gains an import and one term, the way `doctor_starved` and `doctor_auth` are already wired in.

The complaint's own wording is the builder's; the gate holds it only to being about the right card and about no other.

## Done when

The gate passes. Over a temporary backlog holding `P` (`sliced`, empty `Needs`, nobody names it), `Q` (`sliced`, empty `Needs`) with `Q.one` naming `Q` in `sliced_from`, `R` (`sliced`, `needs: [R.a]`) with `R.a` `done`, and `S` (`todo`), `doctor.diagnose` returns exactly one complaint whose `about` is `P`, and no complaint whose `about` is `Q`, `Q.one`, `R`, `R.a` or `S`. `graph/lib/doctor_slices.py` imports. graph/tests/test_doctor.py, graph/tests/test_doctor_salvage.py and graph/tests/test_doctor_starved.py stay green. The gate does not prove the wording of the complaint or of what to do about it, and it does not prove anything about `settled`.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, sys, tempfile
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
import yaml
try:
    import doctor_slices  # noqa: F401
except ImportError:
    sys.exit("a sliced card nobody names is not reported: there is no doctor_slices module")
from backlog import Backlog
from doctor import diagnose
from workspace import Workspace

RED = "a sliced card nobody names is not reported"


def card(task_id, status="todo", needs=(), **extra):
    row = {"id": task_id, "goal": f"do {task_id}", "status": status, "needs": list(needs),
           "files": [], "gate": "true", "done_when": f"{task_id} passes"}
    row.update(extra)
    return row


def book(*rows):
    path = pathlib.Path(tempfile.mkdtemp()) / "backlog.yaml"
    path.write_text(yaml.safe_dump({"schema": "e2e-backlog.v1", "tasks": list(rows)},
                                   sort_keys=False))
    return Backlog(path)


here = Workspace(tempfile.mkdtemp()).init(goal="a probe", backlog="b.yaml")
out = diagnose(book(
    card("P", "sliced"),                   # nothing to settle it: the complaint
    card("Q", "sliced"), card("Q.one", "todo", sliced_from="Q"),   # a card names it
    card("R", "sliced", ["R.a"]), card("R.a", "done"),             # its Needs holds it
    card("S"),
), here)
about = [one.about for one in out]
assert about.count("P") == 1, f"{RED}: complaints about P: {about.count('P')} in {about}"
for settling in ("Q", "Q.one", "R", "R.a", "S"):
    assert settling not in about, \
        f"{RED}: {settling} was reported too, and something can settle it: {about}"
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_doctor)
(cd graph/tests && timeout 600 python3 -m unittest test_doctor_salvage)
(cd graph/tests && timeout 600 python3 -m unittest test_doctor_starved)
```

## Needs

- [[settled-counts-the-cards-that-name-a-parent/molecule]]

## Note

Red today: the probe exits with `a sliced card nobody names is not reported: there is no doctor_slices module`. Every code file stays under 200 lines; graph/lib/doctor.py is 188 lines, so the check goes in the new file and `diagnose` gains an import and one term. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
