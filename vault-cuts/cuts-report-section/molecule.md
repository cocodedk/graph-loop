---
source:
- docs/rfc/jev-cuts-brief.md:73
- docs/rfc/jev-cuts-brief.md:74
files:
- graph/lib/report.py
- graph/lib/report_cuts.py
status: done
expect_red: the report does not sum the cut check
requirement:
  goal: '`report(space)` gains a `cuts` entry summing the `cut_checked` lines in the trace beside the
    campaign''s own backlog — `runs`, `requests`, `seconds`, `usable`, `merges`, `findings` and `failures`
    — and `as_text` prints one line beginning `Cut check`, which says none ran when there are no such
    lines rather than disappearing.'
  done_when: 'The gate passes. Over a campaign whose init event names a backlog holding three `cut_checked`
    lines — one act run of 3 requests, 1.5s, 7 usable and 1 merge; one observe run of 5 requests, 2.5s,
    4 usable and 2 findings; and one that failed — `report(space)["cuts"]` is exactly `{"runs": 3, "requests":
    8, "seconds": 4.0, "usable": 11, "merges": 1, "findings": 2, "failures": 1}`, and `as_text` of it
    holds a line beginning `Cut check`. Over a campaign whose trace holds no `cut_checked` line, that
    entry is the same seven keys at zero and the `Cut check` line says none. graph/tests/test_report.py,
    graph/tests/test_report_decide.py and graph/tests/test_report_review.py stay green.'
  sources:
  - docs/rfc/jev-cuts-brief.md:73
  - docs/rfc/jev-cuts-brief.md:74
replans: 1
replan_history:
- The gate checks only whether text contains `Cut check`; it can pass without the required line beginning
  `Cut check`. Assert exactly one such line in both cases.; The gate never exercises a campaign without
  an init event, so it can pass while reporting raises in the explicitly required no-init case. Add that
  probe without expanding builder write access.
contract_seen: 84ed359b69bc0ff9
accepted_criteria:
  goal: '`report(space)` gains a `cuts` entry that sums the `cut_checked` lines in the trace beside the
    campaign''s own backlog, with the keys `runs`, `requests`, `seconds`, `usable`, `merges`, `findings`
    and `failures`. `as_text` prints exactly one line beginning `Cut check`. That line says none ran when
    there are no such lines, and also when the campaign has no init event and so no backlog. Report never
    raises in either case.'
  gate: "set -e -o pipefail\ntimeout 600 python3 - <<'PY'\nimport json, os, pathlib, sys, tempfile\nroot\
    \ = pathlib.Path(os.getcwd()).resolve()\nsys.path.insert(0, str(root / \"graph\" / \"lib\"))\ntry:\n\
    \    import report_cuts  # noqa: F401\nexcept ImportError:\n    sys.exit(\"the report does not sum\
    \ the cut check: there is no report_cuts module\")\nfrom report import as_text, report\nfrom workspace\
    \ import Workspace\n\nZERO = {\"runs\": 0, \"requests\": 0, \"seconds\": 0.0, \"usable\": 0,\n   \
    \     \"merges\": 0, \"findings\": 0, \"failures\": 0}\n\ndef campaign(lines):\n    backlog = pathlib.Path(tempfile.mkdtemp())\n\
    \    (backlog / \".slicer-trace.jsonl\").write_text(\n        \"\".join(json.dumps(line) + \"\\n\"\
    \ for line in lines), \"utf-8\")\n    space = Workspace(tempfile.mkdtemp())\n    space.init(goal=\"\
    a probe\", backlog=str(backlog))\n    return space\n\ndef checked(**fields):\n    line = {\"at\":\
    \ \"2026-09-20T12:00:00+00:00\", \"step\": \"cut_checked\", \"molecule\": \"m\",\n            \"mode\"\
    : \"act\", \"requests\": 0, \"seconds\": 0.0, \"usable\": 0, \"merges\": 0,\n            \"findings\"\
    : 0, \"failed\": \"\"}\n    line.update(fields)\n    return line\n\ndef cut_lines(out):\n    return\
    \ [one for one in as_text(out).splitlines() if one.startswith(\"Cut check\")]\n\nspace = campaign([\n\
    \    {\"at\": \"2026-09-20T11:59:00+00:00\", \"step\": \"validated\", \"result\": \"MOLECULE\"},\n\
    \    checked(molecule=\"one\", mode=\"act\", requests=3, seconds=1.5, usable=7, merges=1),\n    checked(molecule=\"\
    two\", mode=\"observe\", requests=5, seconds=2.5, usable=4, findings=2),\n    checked(molecule=\"\
    three\", mode=\"\", failed=\"RuntimeError: down\"),\n])\nout = report(space)\nassert out.get(\"cuts\"\
    ) == {\"runs\": 3, \"requests\": 8, \"seconds\": 4.0, \"usable\": 11,\n                          \
    \ \"merges\": 1, \"findings\": 2, \"failures\": 1}, \\\n    f\"the report does not sum the cut check:\
    \ {out.get('cuts')}\"\nlines = cut_lines(out)\nassert len(lines) == 1, f\"expected exactly one line\
    \ beginning 'Cut check': {lines}\"\nassert \"none\" not in lines[0].lower(), f\"the line says none\
    \ although runs exist: {lines}\"\n\nquiet = report(campaign([{\"at\": \"2026-09-20T11:59:00+00:00\"\
    , \"step\": \"validated\"}]))\nassert quiet.get(\"cuts\") == ZERO, f\"the quiet campaign is not all\
    \ zero: {quiet.get('cuts')}\"\nlines = cut_lines(quiet)\nassert len(lines) == 1, f\"expected exactly\
    \ one line beginning 'Cut check': {lines}\"\nassert \"none\" in lines[0].lower(), f\"the line does\
    \ not say none ran: {lines}\"\n\nbare = Workspace(tempfile.mkdtemp())  # no init event, so no backlog\n\
    out = report(bare)\nassert out.get(\"cuts\") == ZERO, f\"the no-init campaign is not all zero: {out.get('cuts')}\"\
    \nlines = cut_lines(out)\nassert len(lines) == 1, f\"expected exactly one line beginning 'Cut check':\
    \ {lines}\"\nassert \"none\" in lines[0].lower(), f\"the line does not say none ran: {lines}\"\nprint(\"\
    PROBE OK\")\nPY\n(cd graph/tests && timeout 600 python3 -m unittest test_report)\n(cd graph/tests\
    \ && timeout 600 python3 -m unittest test_report_decide)\n(cd graph/tests && timeout 600 python3 -m\
    \ unittest test_report_review)\n"
  done_when: 'The gate passes. Over a campaign whose init event names a backlog holding three `cut_checked`
    lines (one act run of 3 requests, 1.5s, 7 usable and 1 merge; one observe run of 5 requests, 2.5s,
    4 usable and 2 findings; one that failed), `report(space)["cuts"]` is exactly `{"runs": 3, "requests":
    8, "seconds": 4.0, "usable": 11, "merges": 1, "findings": 2, "failures": 1}`. `as_text` of it has
    exactly one line beginning `Cut check`, and that line does not say none. Over a campaign whose trace
    holds no `cut_checked` line, and over a campaign with no init event at all, `report` does not raise.
    The entry is the same seven keys at zero, and `as_text` has exactly one line beginning `Cut check`,
    which says none. graph/tests/test_report.py, graph/tests/test_report_decide.py and graph/tests/test_report_review.py
    stay green. The gate proves the sums, the zero case, the no-init case, the exactly-one-line rule,
    and that `report_cuts` imports. It does not prove the wording of the line beyond `Cut check` and the
    word none, and it does not prove how the line looks when runs exist beyond its start.'
  files:
  - graph/lib/report.py
  - graph/lib/report_cuts.py
rebuild_from: /var/tmp/graph-trees/graph-gc529051/task-cuts-report-section
session: fb5de424-477c-470a-a9b1-a815cf9d71dc
session_account: personal

commit: c3fb81ed9abf87402fcc5a89d5398adddf8b9e7c
worktree: /var/tmp/graph-trees/graph-gc529051/task-cuts-report-section
kept_at: '2026-09-20T18:15:53Z'
---

## Goal

`report(space)` gains a `cuts` entry that sums the `cut_checked` lines in the trace beside the campaign's own backlog, with the keys `runs`, `requests`, `seconds`, `usable`, `merges`, `findings` and `failures`. `as_text` prints exactly one line beginning `Cut check`. That line says none ran when there are no such lines, and also when the campaign has no init event and so no backlog. Report never raises in either case.

## Why

The brief's behaviour 5 says the report gains one section: requests, seconds, usable verdicts, merges applied, findings raised. Nothing reads those numbers back today, so a campaign running the cut check cannot say what it bought.

## Done when

The gate passes. Over a campaign whose init event names a backlog holding three `cut_checked` lines (one act run of 3 requests, 1.5s, 7 usable and 1 merge; one observe run of 5 requests, 2.5s, 4 usable and 2 findings; one that failed), `report(space)["cuts"]` is exactly `{"runs": 3, "requests": 8, "seconds": 4.0, "usable": 11, "merges": 1, "findings": 2, "failures": 1}`. `as_text` of it has exactly one line beginning `Cut check`, and that line does not say none. Over a campaign whose trace holds no `cut_checked` line, and over a campaign with no init event at all, `report` does not raise. The entry is the same seven keys at zero, and `as_text` has exactly one line beginning `Cut check`, which says none. graph/tests/test_report.py, graph/tests/test_report_decide.py and graph/tests/test_report_review.py stay green. The gate proves the sums, the zero case, the no-init case, the exactly-one-line rule, and that `report_cuts` imports. It does not prove the wording of the line beyond `Cut check` and the word none, and it does not prove how the line looks when runs exist beyond its start.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import json, os, pathlib, sys, tempfile
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
try:
    import report_cuts  # noqa: F401
except ImportError:
    sys.exit("the report does not sum the cut check: there is no report_cuts module")
from report import as_text, report
from workspace import Workspace

ZERO = {"runs": 0, "requests": 0, "seconds": 0.0, "usable": 0,
        "merges": 0, "findings": 0, "failures": 0}

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

def cut_lines(out):
    return [one for one in as_text(out).splitlines() if one.startswith("Cut check")]

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
lines = cut_lines(out)
assert len(lines) == 1, f"expected exactly one line beginning 'Cut check': {lines}"
assert "none" not in lines[0].lower(), f"the line says none although runs exist: {lines}"

quiet = report(campaign([{"at": "2026-09-20T11:59:00+00:00", "step": "validated"}]))
assert quiet.get("cuts") == ZERO, f"the quiet campaign is not all zero: {quiet.get('cuts')}"
lines = cut_lines(quiet)
assert len(lines) == 1, f"expected exactly one line beginning 'Cut check': {lines}"
assert "none" in lines[0].lower(), f"the line does not say none ran: {lines}"

bare = Workspace(tempfile.mkdtemp())  # no init event, so no backlog
out = report(bare)
assert out.get("cuts") == ZERO, f"the no-init campaign is not all zero: {out.get('cuts')}"
lines = cut_lines(out)
assert len(lines) == 1, f"expected exactly one line beginning 'Cut check': {lines}"
assert "none" in lines[0].lower(), f"the line does not say none ran: {lines}"
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
