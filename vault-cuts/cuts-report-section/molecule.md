---
source:
- docs/rfc/jev-cuts-brief.md:73
- docs/rfc/jev-cuts-brief.md:74
files:
- graph/lib/report.py
- graph/lib/report_cuts.py
status: todo
gate_reviewed_first: true
expect_red: the report does not sum the cut check
---

## Goal

`report(space)` gains a `cuts` entry summing the `cut_checked` lines in the trace beside the campaign's own backlog — `runs`, `requests`, `seconds`, `usable`, `merges`, `findings` and `failures` — and `as_text` prints one line beginning `Cut check`, which says none ran when there are no such lines rather than disappearing.

## Why

The brief's behaviour 5 says the report gains one section: requests, seconds, usable verdicts, merges applied, findings raised. Nothing reads those numbers back today, so a campaign running the cut check cannot say what it bought.

## Done when

The gate passes. Over a campaign whose init event names a backlog holding three `cut_checked` lines — one act run of 3 requests, 1.5s, 7 usable and 1 merge; one observe run of 5 requests, 2.5s, 4 usable and 2 findings; and one that failed — `report(space)["cuts"]` is exactly `{"runs": 3, "requests": 8, "seconds": 4.0, "usable": 11, "merges": 1, "findings": 2, "failures": 1}`, and `as_text` of it holds a line beginning `Cut check`. Over a campaign whose trace holds no `cut_checked` line, that entry is the same seven keys at zero and the `Cut check` line says none. graph/tests/test_report.py, graph/tests/test_report_decide.py and graph/tests/test_report_review.py stay green.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import json, os, pathlib, sys, tempfile
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
from report import as_text, report
from workspace import Workspace

def campaign(lines):
    backlog = pathlib.Path(tempfile.mkdtemp())
    (backlog / ".slicer-trace.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in lines), "utf-8")
    space = Workspace(tempfile.mkdtemp())
    space.init(goal="a probe", backlog=str(backlog))
    return space

def checked(**fields):
    line = {"at": "2026-09-20T12:00:00+00:00", "step": "cut_checked", "molecule": "m",
            "mode": "act", "requests": 0, "seconds": 0.0, "usable": 0, "merges": 0,
            "findings": 0, "failed": ""}
    line.update(fields)
    return line

space = campaign([
    {"at": "2026-09-20T11:59:00+00:00", "step": "validated", "result": "MOLECULE"},
    checked(molecule="one", mode="act", requests=3, seconds=1.5, usable=7, merges=1),
    checked(molecule="two", mode="observe", requests=5, seconds=2.5, usable=4, findings=2),
    checked(molecule="three", mode="", failed="RuntimeError: down"),
])
out = report(space)
assert out.get("cuts") == {"runs": 3, "requests": 8, "seconds": 4.0, "usable": 11,
                           "merges": 1, "findings": 2, "failures": 1}, \
    f"the report does not sum the cut check: {out.get('cuts')}"
text = as_text(out)
assert "Cut check" in text, f"the report does not sum the cut check into a section:\n{text}"

quiet = report(campaign([{"at": "2026-09-20T11:59:00+00:00", "step": "validated"}]))
assert quiet.get("cuts") == {"runs": 0, "requests": 0, "seconds": 0.0, "usable": 0,
                             "merges": 0, "findings": 0, "failures": 0}, \
    f"the report does not sum the cut check: {quiet.get('cuts')}"
said = as_text(quiet)
assert "Cut check" in said, f"the section vanished when nothing ran:\n{said}"
line = [one for one in said.splitlines() if "Cut check" in one]
assert line and "none" in line[0].lower(), f"the section does not say none ran: {line}"
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_report)
(cd graph/tests && timeout 600 python3 -m unittest test_report_decide)
(cd graph/tests && timeout 600 python3 -m unittest test_report_review)
```

## Needs

- [[cut-checked-trace-carries-the-counts/molecule]]

## Note

Red today: `the report does not sum the cut check: None` — `report` has no `cuts` entry. `campaign_of.backlog_of(space)` is how a campaign already learns where its backlog is, and it answers `""` for a campaign with no init event, which a report must survive rather than raise on. graph/lib/report.py is 184 lines today, so the reading and the wording belong in graph/lib/report_cuts.py to keep every code file under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
