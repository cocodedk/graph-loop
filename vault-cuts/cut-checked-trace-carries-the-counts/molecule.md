---
source:
- docs/rfc/jev-cuts-brief.md:63
- docs/rfc/jev-cuts-brief.md:74
files:
- slicer/cut_check.py
- slicer/slicer_answer.py
status: done
expect_red: the trace line does not carry the counts
requirement:
  goal: 'Every run of the cut check leaves exactly one `cut_checked` line in the backlog''s `.slicer-trace.jsonl`
    and no other line about that run: it carries the molecule''s name, the `mode` it ran in, the `requests`
    sent to the decisions model, the `seconds` the asking took, the `usable` verdicts, the `merges` applied,
    the `findings` raised, and `failed` — empty when the check ran, and the exception''s type and message
    when the checker raised, with `mode` empty and every count zero.'
  done_when: 'The gate passes. Through `run_answer` with a checker built by `cut_hook.make_checker`, on
    a two-atom molecule that `validate()` returned: with the campaign switched off, the one line says
    mode `off` and every count 0; switched to act with a scripted model answering keep_together and pass
    everywhere, it says mode `act`, requests 3, usable 7, merges 1, findings 0, failed empty; with the
    same model answering split and failing beta''s one_job, it says requests 3, usable 7, merges 0, findings
    1; and with a checker that raises `RuntimeError("cut-probe-boom")`, it says mode empty, every count
    0, and a `failed` carrying both `RuntimeError` and `cut-probe-boom`. Each run leaves exactly one `cut_checked`
    line, no `cut_check_failed` line, and a `seconds` that is a number at or above zero. slicer/tests/test_cut_check.py,
    slicer/tests/test_slicer_cut_check.py and slicer/tests/test_slicer.py stay green.'
  sources:
  - docs/rfc/jev-cuts-brief.md:63
  - docs/rfc/jev-cuts-brief.md:74
replans: 2
replan_history:
- The gate accepts seconds=0 for every run, so it does not prove that seconds measures the time spent
  asking.; The gate never checks observe-mode trace counts or distinguishes usable verdicts from all verdicts;
  incorrect accounting can pass. No recorded narrowing decision is named.; The crash case omits the molecule-name
  assertion, and the gate forbids only cut_check_failed rather than every additio
- 'The gate permits timing the entire checker instead of only asking; its act threshold also permits timing
  just one of three requests. The note names no recorded decision narrowing the frozen timing requirement.;
  The unusable-reply probe cannot distinguish counting all returned verdicts from counting usable verdicts:
  cut_verdicts.read already drops non-ok replies. Add an ok reply with below-threshol'
contract_seen: e08393a5c2c465e5
accepted_criteria:
  goal: Every run of the cut check leaves exactly one `cut_checked` line in the backlog's `.slicer-trace.jsonl`,
    and that line is the only record of the run. It carries the molecule's name, the `mode` it ran in,
    the `requests` sent to the decisions model, the `seconds` spent inside those requests (the sum of
    how long each request took, so checker work outside the requests is not counted), the `usable` verdicts
    (ok replies whose confidence clears the 0.6 gate, not every verdict), the `merges` applied, the `findings`
    raised, and `failed`. `failed` is empty when the check ran. When the checker raised, `failed` holds
    the exception's type and message, `mode` is empty, and every count is zero.
  gate: "set -e -o pipefail\ntimeout 600 python3 - <<'PY'\nimport json, os, pathlib, sys, tempfile, time,\
    \ types\nroot = pathlib.Path(os.getcwd()).resolve()\nsys.path.insert(0, str(root / \"graph\" / \"\
    lib\"))\nsys.path.insert(0, str(root / \"slicer\"))\nimport yaml\nimport cut_states\nimport slicer\n\
    from cut_hook import make_checker\nfrom intelligence import Reply\n\nSPENT = []\n\ndef atom(name,\
    \ stage):\n    return {\"name\": name, \"stage\": stage, \"goal\": f\"do {name}\", \"files\": [\"\
    app.py\"],\n            \"gate\": \"set -e -o pipefail\\nfalse\", \"done_when\": f\"{name} is proved\"\
    }\n\nANSWER = {\"result\": \"MOLECULE\", \"reason\": \"one gap\", \"molecule\": {\n    \"name\": \"\
    greeting\", \"source\": [\"specs/greeting.md:1\"], \"goal\": \"return a greeting\",\n    \"why\":\
    \ \"the function is absent\", \"needs\": [],\n    \"atoms\": [atom(\"alpha\", 1), atom(\"beta\", 2)]}}\n\
    \ndef scripted(cut=\"keep_together\", fail_atom=None, ok=True, delay=0.3, weak=None):\n    def ask(state,\
    \ questions):\n        began = time.monotonic()\n        time.sleep(delay)\n        out = {}\n   \
    \     for question in questions:\n            choice = cut if question == \"cut\" else \"pass\"\n\
    \            if fail_atom and question == \"one_job\" \\\n                    and state.get(\"atom\"\
    , {}).get(\"name\") == fail_atom:\n                choice = \"fail\"\n            out[question] =\
    \ {\"choice\": choice,\n                             \"confidence\": 0.1 if question == weak else\
    \ 0.9}\n        SPENT.append(time.monotonic() - began)\n        return types.SimpleNamespace(ok=ok,\
    \ answers=out if ok else {})\n    return ask\n\ndef run(mode, checker):\n    SPENT.clear()\n    repo\
    \ = pathlib.Path(tempfile.mkdtemp())\n    backlog, specs, campaign = repo / \"backlog\", repo / \"\
    specs\", repo / \"campaign\"\n    for made in (backlog, specs, campaign):\n        made.mkdir()\n\
    \    (specs / \"greeting.md\").write_text(\"## Goal\\nReturn a greeting.\\n\", \"utf-8\")\n    (repo\
    \ / \"app.py\").write_text(\"present = True\\n\", \"utf-8\")\n    if mode != \"off\":\n        cut_states.switch(campaign,\
    \ mode, \"probe\")\n    try:\n        slicer.run_answer(yaml.safe_dump(ANSWER), repo=repo, backlog=backlog,\n\
    \                          sources=[specs],\n                          reviewer=lambda question: Reply(True,\
    \ \"ok\"),\n                          checker=checker(campaign))\n    except Exception:\n        pass\n\
    \    path = backlog / \".slicer-trace.jsonl\"\n    rows = [json.loads(line) for line in path.read_text(\"\
    utf-8\").splitlines()] \\\n        if path.exists() else []\n    said = [row for row in rows if row.get(\"\
    step\") == \"cut_checked\"]\n    assert len(said) == 1, f\"a run left {len(said)} cut_checked lines,\
    \ not one: {rows}\"\n    other = [row for row in rows if row is not said[0]\n             and (str(row.get(\"\
    step\", \"\")).startswith(\"cut\") or \"cut_check\" in json.dumps(row))]\n    assert not other, f\"\
    another line still records the cut check: {other}\"\n    row = dict(said[0])\n    row[\"_spent\"]\
    \ = sum(SPENT)\n    return row\n\ndef counts(row):\n    return {key: row.get(key) for key in\n   \
    \         (\"molecule\", \"mode\", \"requests\", \"usable\", \"merges\", \"findings\", \"failed\"\
    )}\n\ndef asking(**how):\n    def build(campaign):\n        inner = make_checker(campaign, None, scripted(**how))\n\
    \        def checker(molecule):\n            time.sleep(0.4)\n            out = inner(molecule)\n\
    \            time.sleep(0.4)\n            return out\n        return checker\n    return build\n\n\
    def only_asking(row):\n    spent, seconds = row[\"_spent\"], row[\"seconds\"]\n    assert spent >=\
    \ 0.85, f\"the probe did not ask three times: {spent}\"\n    assert spent - 0.001 <= seconds <= spent\
    \ + 0.15, \\\n        f\"seconds is not the time spent in the requests ({spent}): {row}\"\n\noff =\
    \ run(\"off\", asking())\nassert counts(off) == {\"molecule\": \"greeting\", \"mode\": \"off\", \"\
    requests\": 0, \"usable\": 0,\n                       \"merges\": 0, \"findings\": 0, \"failed\":\
    \ \"\"}, \\\n    f\"the trace line does not carry the counts: {counts(off)}\"\nassert off[\"seconds\"\
    ] < 0.15, f\"seconds counts work outside the requests: {off}\"\n\nacted = run(\"act\", asking())\n\
    assert counts(acted) == {\"molecule\": \"greeting\", \"mode\": \"act\", \"requests\": 3, \"usable\"\
    : 7,\n                         \"merges\": 1, \"findings\": 0, \"failed\": \"\"}, \\\n    f\"the trace\
    \ line does not carry the counts: {counts(acted)}\"\nonly_asking(acted)\n\nseen = run(\"observe\"\
    , asking())\nassert counts(seen) == {\"molecule\": \"greeting\", \"mode\": \"observe\", \"requests\"\
    : 3,\n                        \"usable\": 7, \"merges\": 0, \"findings\": 0, \"failed\": \"\"}, \\\
    \n    f\"the observe line does not carry the counts: {counts(seen)}\"\nonly_asking(seen)\n\nsplit\
    \ = run(\"act\", asking(cut=\"split\", fail_atom=\"beta\"))\nassert counts(split) == {\"molecule\"\
    : \"greeting\", \"mode\": \"act\", \"requests\": 3, \"usable\": 7,\n                         \"merges\"\
    : 0, \"findings\": 1, \"failed\": \"\"}, \\\n    f\"the trace line does not carry the counts: {counts(split)}\"\
    \n\ndead = run(\"act\", asking(ok=False))\nassert dead.get(\"requests\", 0) > 0 and dead.get(\"usable\"\
    ) == 0 and dead.get(\"merges\") == 0, \\\n    f\"usable counts unusable replies: {counts(dead)}\"\n\
    \nweak = run(\"act\", asking(weak=\"cut\"))\nassert weak.get(\"requests\") == 3 and weak.get(\"usable\"\
    ) == 6 and weak.get(\"merges\") == 0, \\\n    f\"usable counts an ok reply below the confidence gate:\
    \ {counts(weak)}\"\n\ndef raiser(campaign):\n    def checker(molecule):\n        raise RuntimeError(\"\
    cut-probe-boom\")\n    return checker\n\ncrashed = run(\"act\", raiser)\nassert crashed.get(\"molecule\"\
    ) == \"greeting\" and crashed.get(\"mode\") == \"\" \\\n    and crashed.get(\"requests\") == 0 and\
    \ crashed.get(\"usable\") == 0 \\\n    and crashed.get(\"merges\") == 0 and crashed.get(\"findings\"\
    ) == 0, \\\n    f\"the trace line does not carry the counts: {counts(crashed)}\"\nassert \"RuntimeError\"\
    \ in str(crashed.get(\"failed\")) \\\n    and \"cut-probe-boom\" in str(crashed.get(\"failed\")),\
    \ \\\n    f\"the trace line does not name the failure: {counts(crashed)}\"\n\nfor row in (off, acted,\
    \ seen, split, dead, weak, crashed):\n    seconds = row.get(\"seconds\")\n    assert isinstance(seconds,\
    \ (int, float)) and not isinstance(seconds, bool) \\\n        and seconds >= 0, f\"the line carries\
    \ no wall time: {row}\"\nprint(\"PROBE OK\")\nPY\n(cd slicer/tests && timeout 600 python3 -m unittest\
    \ test_cut_check)\n(cd slicer/tests && timeout 600 python3 -m unittest test_slicer_cut_check)\n(cd\
    \ slicer/tests && timeout 600 python3 -m unittest test_slicer)\n"
  done_when: 'The gate passes. Each run goes through `run_answer` with a checker built by `cut_hook.make_checker`,
    on a two-atom molecule that `validate()` returned, and leaves exactly one line whose step is `cut_checked`.
    No other line mentions the cut check: no `cut_check_failed`, and no other step starting with `cut`.
    `seconds` is defined as the summed duration of the requests; this fixes the meaning of the existing
    field and relaxes nothing. Expected lines. Switched off: mode `off`, every count 0, failed empty,
    `seconds` under 0.15 even though the gate wraps the checker in 0.8s of its own delay outside the requests.
    Act with a scripted model answering keep_together and pass: mode `act`, requests 3, usable 7, merges
    1, findings 0, failed empty, and `seconds` between the sum of the durations the scripted model measured
    for its own three 0.3s requests and that sum plus 0.15. That range fails if only one request is timed,
    and it also fails if the whole checker is timed, because of the 0.8s outside delay. Observe with the
    same model: mode `observe`, requests 3, usable 7, merges 0, findings 0. Act with the model answering
    split and failing beta''s one_job: requests 3, usable 7, merges 0, findings 1. Act with a model whose
    every reply is not ok: requests above 0, usable 0, merges 0. Act with a model whose replies are all
    ok but whose confidence on the `cut` question is 0.1: requests 3, usable 6, merges 0, which shows
    `usable` drops ok replies below the gate and is not the count of all verdicts. A checker raising `RuntimeError("cut-probe-boom")`:
    molecule `greeting`, mode empty, every count 0, and `failed` carrying both `RuntimeError` and `cut-probe-boom`.
    `seconds` is a number at or above 0 on every line. The three unit-test modules stay green. The gate
    proves the line''s shape, counts, uniqueness, and that `seconds` covers exactly the requests. It does
    not pin `seconds` on the crash line, and it does not pin the findings count of the unusable-reply
    runs.'
  files:
  - slicer/cut_check.py
  - slicer/slicer_answer.py
rebuild_from: /var/tmp/graph-trees/graph-o27dt4mc/task-cut-checked-trace-carries-the-counts
session: b328766b-bf93-4828-a0f6-ff8f1af59438
session_account: personal

commit: cc2ae7b0cc5c3327ed4774a204529ca9301422df
worktree: /var/tmp/graph-trees/graph-o27dt4mc/task-cut-checked-trace-carries-the-counts
kept_at: '2026-09-20T18:11:32Z'
---

## Goal

Every run of the cut check leaves exactly one `cut_checked` line in the backlog's `.slicer-trace.jsonl`, and that line is the only record of the run. It carries the molecule's name, the `mode` it ran in, the `requests` sent to the decisions model, the `seconds` spent inside those requests (the sum of how long each request took, so checker work outside the requests is not counted), the `usable` verdicts (ok replies whose confidence clears the 0.6 gate, not every verdict), the `merges` applied, the `findings` raised, and `failed`. `failed` is empty when the check ran. When the checker raised, `failed` holds the exception's type and message, `mode` is empty, and every count is zero.

## Why

Behaviour 5 wants the campaign's report to say how many requests, seconds, usable verdicts, merges and findings the cut check produced, and behaviour 4 wants a failure to say why. The trace line the slicer writes today carries a finding count and nothing else, so none of those numbers is recorded anywhere and a crash is written as a second, differently shaped line.

## Done when

The gate passes. Each run goes through `run_answer` with a checker built by `cut_hook.make_checker`, on a two-atom molecule that `validate()` returned, and leaves exactly one line whose step is `cut_checked`. No other line mentions the cut check: no `cut_check_failed`, and no other step starting with `cut`. `seconds` is defined as the summed duration of the requests; this fixes the meaning of the existing field and relaxes nothing. Expected lines. Switched off: mode `off`, every count 0, failed empty, `seconds` under 0.15 even though the gate wraps the checker in 0.8s of its own delay outside the requests. Act with a scripted model answering keep_together and pass: mode `act`, requests 3, usable 7, merges 1, findings 0, failed empty, and `seconds` between the sum of the durations the scripted model measured for its own three 0.3s requests and that sum plus 0.15. That range fails if only one request is timed, and it also fails if the whole checker is timed, because of the 0.8s outside delay. Observe with the same model: mode `observe`, requests 3, usable 7, merges 0, findings 0. Act with the model answering split and failing beta's one_job: requests 3, usable 7, merges 0, findings 1. Act with a model whose every reply is not ok: requests above 0, usable 0, merges 0. Act with a model whose replies are all ok but whose confidence on the `cut` question is 0.1: requests 3, usable 6, merges 0, which shows `usable` drops ok replies below the gate and is not the count of all verdicts. A checker raising `RuntimeError("cut-probe-boom")`: molecule `greeting`, mode empty, every count 0, and `failed` carrying both `RuntimeError` and `cut-probe-boom`. `seconds` is a number at or above 0 on every line. The three unit-test modules stay green. The gate proves the line's shape, counts, uniqueness, and that `seconds` covers exactly the requests. It does not pin `seconds` on the crash line, and it does not pin the findings count of the unusable-reply runs.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import json, os, pathlib, sys, tempfile, time, types
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
sys.path.insert(0, str(root / "slicer"))
import yaml
import cut_states
import slicer
from cut_hook import make_checker
from intelligence import Reply

SPENT = []

def atom(name, stage):
    return {"name": name, "stage": stage, "goal": f"do {name}", "files": ["app.py"],
            "gate": "set -e -o pipefail\nfalse", "done_when": f"{name} is proved"}

ANSWER = {"result": "MOLECULE", "reason": "one gap", "molecule": {
    "name": "greeting", "source": ["specs/greeting.md:1"], "goal": "return a greeting",
    "why": "the function is absent", "needs": [],
    "atoms": [atom("alpha", 1), atom("beta", 2)]}}

def scripted(cut="keep_together", fail_atom=None, ok=True, delay=0.3, weak=None):
    def ask(state, questions):
        began = time.monotonic()
        time.sleep(delay)
        out = {}
        for question in questions:
            choice = cut if question == "cut" else "pass"
            if fail_atom and question == "one_job" \
                    and state.get("atom", {}).get("name") == fail_atom:
                choice = "fail"
            out[question] = {"choice": choice,
                             "confidence": 0.1 if question == weak else 0.9}
        SPENT.append(time.monotonic() - began)
        return types.SimpleNamespace(ok=ok, answers=out if ok else {})
    return ask

def run(mode, checker):
    SPENT.clear()
    repo = pathlib.Path(tempfile.mkdtemp())
    backlog, specs, campaign = repo / "backlog", repo / "specs", repo / "campaign"
    for made in (backlog, specs, campaign):
        made.mkdir()
    (specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")
    (repo / "app.py").write_text("present = True\n", "utf-8")
    if mode != "off":
        cut_states.switch(campaign, mode, "probe")
    try:
        slicer.run_answer(yaml.safe_dump(ANSWER), repo=repo, backlog=backlog,
                          sources=[specs],
                          reviewer=lambda question: Reply(True, "ok"),
                          checker=checker(campaign))
    except Exception:
        pass
    path = backlog / ".slicer-trace.jsonl"
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines()] \
        if path.exists() else []
    said = [row for row in rows if row.get("step") == "cut_checked"]
    assert len(said) == 1, f"a run left {len(said)} cut_checked lines, not one: {rows}"
    other = [row for row in rows if row is not said[0]
             and (str(row.get("step", "")).startswith("cut") or "cut_check" in json.dumps(row))]
    assert not other, f"another line still records the cut check: {other}"
    row = dict(said[0])
    row["_spent"] = sum(SPENT)
    return row

def counts(row):
    return {key: row.get(key) for key in
            ("molecule", "mode", "requests", "usable", "merges", "findings", "failed")}

def asking(**how):
    def build(campaign):
        inner = make_checker(campaign, None, scripted(**how))
        def checker(molecule):
            time.sleep(0.4)
            out = inner(molecule)
            time.sleep(0.4)
            return out
        return checker
    return build

def only_asking(row):
    spent, seconds = row["_spent"], row["seconds"]
    assert spent >= 0.85, f"the probe did not ask three times: {spent}"
    assert spent - 0.001 <= seconds <= spent + 0.15, \
        f"seconds is not the time spent in the requests ({spent}): {row}"

off = run("off", asking())
assert counts(off) == {"molecule": "greeting", "mode": "off", "requests": 0, "usable": 0,
                       "merges": 0, "findings": 0, "failed": ""}, \
    f"the trace line does not carry the counts: {counts(off)}"
assert off["seconds"] < 0.15, f"seconds counts work outside the requests: {off}"

acted = run("act", asking())
assert counts(acted) == {"molecule": "greeting", "mode": "act", "requests": 3, "usable": 7,
                         "merges": 1, "findings": 0, "failed": ""}, \
    f"the trace line does not carry the counts: {counts(acted)}"
only_asking(acted)

seen = run("observe", asking())
assert counts(seen) == {"molecule": "greeting", "mode": "observe", "requests": 3,
                        "usable": 7, "merges": 0, "findings": 0, "failed": ""}, \
    f"the observe line does not carry the counts: {counts(seen)}"
only_asking(seen)

split = run("act", asking(cut="split", fail_atom="beta"))
assert counts(split) == {"molecule": "greeting", "mode": "act", "requests": 3, "usable": 7,
                         "merges": 0, "findings": 1, "failed": ""}, \
    f"the trace line does not carry the counts: {counts(split)}"

dead = run("act", asking(ok=False))
assert dead.get("requests", 0) > 0 and dead.get("usable") == 0 and dead.get("merges") == 0, \
    f"usable counts unusable replies: {counts(dead)}"

weak = run("act", asking(weak="cut"))
assert weak.get("requests") == 3 and weak.get("usable") == 6 and weak.get("merges") == 0, \
    f"usable counts an ok reply below the confidence gate: {counts(weak)}"

def raiser(campaign):
    def checker(molecule):
        raise RuntimeError("cut-probe-boom")
    return checker

crashed = run("act", raiser)
assert crashed.get("molecule") == "greeting" and crashed.get("mode") == "" \
    and crashed.get("requests") == 0 and crashed.get("usable") == 0 \
    and crashed.get("merges") == 0 and crashed.get("findings") == 0, \
    f"the trace line does not carry the counts: {counts(crashed)}"
assert "RuntimeError" in str(crashed.get("failed")) \
    and "cut-probe-boom" in str(crashed.get("failed")), \
    f"the trace line does not name the failure: {counts(crashed)}"

for row in (off, acted, seen, split, dead, weak, crashed):
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
