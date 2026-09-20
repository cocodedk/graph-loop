---
source:
- docs/rfc/jev-cuts-brief.md:63
- docs/rfc/jev-cuts-brief.md:74
files:
- slicer/cut_check.py
- slicer/slicer_answer.py
status: todo
gate_reviewed_first: true
expect_red: the trace line does not carry the counts
---

## Goal

Every run of the cut check leaves exactly one `cut_checked` line in the backlog's `.slicer-trace.jsonl` and no other line about that run: it carries the molecule's name, the `mode` it ran in, the `requests` sent to the decisions model, the `seconds` the asking took, the `usable` verdicts, the `merges` applied, the `findings` raised, and `failed` — empty when the check ran, and the exception's type and message when the checker raised, with `mode` empty and every count zero.

## Why

Behaviour 5 wants the campaign's report to say how many requests, seconds, usable verdicts, merges and findings the cut check produced, and behaviour 4 wants a failure to say why. The trace line the slicer writes today carries a finding count and nothing else, so none of those numbers is recorded anywhere and a crash is written as a second, differently shaped line.

## Done when

The gate passes. Through `run_answer` with a checker built by `cut_hook.make_checker`, on a two-atom molecule that `validate()` returned: with the campaign switched off, the one line says mode `off` and every count 0; switched to act with a scripted model answering keep_together and pass everywhere, it says mode `act`, requests 3, usable 7, merges 1, findings 0, failed empty; with the same model answering split and failing beta's one_job, it says requests 3, usable 7, merges 0, findings 1; and with a checker that raises `RuntimeError("cut-probe-boom")`, it says mode empty, every count 0, and a `failed` carrying both `RuntimeError` and `cut-probe-boom`. Each run leaves exactly one `cut_checked` line, no `cut_check_failed` line, and a `seconds` that is a number at or above zero. slicer/tests/test_cut_check.py, slicer/tests/test_slicer_cut_check.py and slicer/tests/test_slicer.py stay green.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import json, os, pathlib, sys, tempfile, types
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
sys.path.insert(0, str(root / "slicer"))
import yaml
import cut_states
import slicer
from cut_hook import make_checker
from intelligence import Reply

def atom(name, stage):
    return {"name": name, "stage": stage, "goal": f"do {name}", "files": ["app.py"],
            "gate": "set -e -o pipefail\nfalse", "done_when": f"{name} is proved"}

ANSWER = {"result": "MOLECULE", "reason": "one gap", "molecule": {
    "name": "greeting", "source": ["specs/greeting.md:1"], "goal": "return a greeting",
    "why": "the function is absent", "needs": [],
    "atoms": [atom("alpha", 1), atom("beta", 2)]}}

def scripted(cut="keep_together", fail_atom=None):
    def ask(state, questions):
        out = {}
        for question in questions:
            choice = cut if question == "cut" else "pass"
            if fail_atom and question == "one_job" \
                    and state.get("atom", {}).get("name") == fail_atom:
                choice = "fail"
            out[question] = {"choice": choice, "confidence": 0.9}
        return types.SimpleNamespace(ok=True, answers=out)
    return ask

def run(mode, checker):
    repo = pathlib.Path(tempfile.mkdtemp())
    backlog, specs, campaign = repo / "backlog", repo / "specs", repo / "campaign"
    for made in (backlog, specs, campaign):
        made.mkdir()
    (specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")
    (repo / "app.py").write_text("present = True\n", "utf-8")
    if mode != "off":
        cut_states.switch(campaign, mode, "probe")
    try:
        slicer.run_answer(yaml.safe_dump(ANSWER), repo=repo, backlog=backlog, sources=[specs],
                          reviewer=lambda question: Reply(True, "ok"),
                          checker=checker(campaign))
    except Exception:
        pass
    path = backlog / ".slicer-trace.jsonl"
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines()] \
        if path.exists() else []
    said = [row for row in rows if row.get("step") == "cut_checked"]
    assert len(said) == 1, f"a run left {len(said)} cut_checked lines, not one: {rows}"
    assert not [row for row in rows if row.get("step") == "cut_check_failed"], \
        f"a second kind of line still records the cut check: {rows}"
    return said[0]

def counts(row):
    return {key: row.get(key) for key in
            ("molecule", "mode", "requests", "usable", "merges", "findings", "failed")}

def asking(**how):
    return lambda campaign: make_checker(campaign, None, scripted(**how))

off = run("off", asking())
assert counts(off) == {"molecule": "greeting", "mode": "off", "requests": 0, "usable": 0,
                       "merges": 0, "findings": 0, "failed": ""}, \
    f"the trace line does not carry the counts: {counts(off)}"

acted = run("act", asking())
assert counts(acted) == {"molecule": "greeting", "mode": "act", "requests": 3, "usable": 7,
                         "merges": 1, "findings": 0, "failed": ""}, \
    f"the trace line does not carry the counts: {counts(acted)}"

split = run("act", asking(cut="split", fail_atom="beta"))
assert counts(split) == {"molecule": "greeting", "mode": "act", "requests": 3, "usable": 7,
                         "merges": 0, "findings": 1, "failed": ""}, \
    f"the trace line does not carry the counts: {counts(split)}"

def raiser(campaign):
    def checker(molecule):
        raise RuntimeError("cut-probe-boom")
    return checker

crashed = run("act", raiser)
assert crashed.get("mode") == "" and crashed.get("requests") == 0 \
    and crashed.get("usable") == 0 and crashed.get("merges") == 0 \
    and crashed.get("findings") == 0, \
    f"the trace line does not carry the counts: {counts(crashed)}"
assert "RuntimeError" in str(crashed.get("failed")) \
    and "cut-probe-boom" in str(crashed.get("failed")), \
    f"the trace line does not name the failure: {counts(crashed)}"

for row in (off, acted, split, crashed):
    seconds = row.get("seconds")
    assert isinstance(seconds, (int, float)) and not isinstance(seconds, bool) \
        and seconds >= 0, f"the line carries no wall time: {row}"
print("PROBE OK")
PY
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_check)
(cd slicer/tests && timeout 600 python3 -m unittest test_slicer_cut_check)
(cd slicer/tests && timeout 600 python3 -m unittest test_slicer)
```

## Note

Red today: `the trace line does not carry the counts: {'molecule': None, 'mode': None, 'requests': None, 'usable': None, 'merges': None, 'findings': 0, 'failed': None}` — the line holds a finding count and nothing else. `requests` is one call per cut and one per atom, not one per question, which is why two atoms give three. slicer/tests/test_slicer_cut_check.py hands `run_answer` a checker whose result carries only `molecule` and `findings`, and the gate runs it, so the counts have to be read off the result without requiring it to carry them. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
