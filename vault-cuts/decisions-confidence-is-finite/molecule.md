---
source:
- docs/rfc/jev-cuts-brief.md:41
- docs/rfc/jev-cuts-brief.md:53
files:
- graph/lib/decisions.py
status: done
expect_red: came back usable
requirement:
  goal: graph/lib/decisions.py answers a reply whose confidence is Infinity, -Infinity, NaN, 1.5 or -0.1
    with no usable answer — either not ok, or a confidence of None — and answers a reply whose confidence
    is 0.0, 0.6, 0.61 or 1.0 with ok, that same number and its choice unchanged.
  done_when: The gate passes. Through `ask()` with a stubbed `post`, a reply whose confidence is `Infinity`,
    `-Infinity`, `NaN`, `1.5` or `-0.1` comes back either not ok or with its confidence `None`. A reply
    whose confidence is `0.6`, `0.61`, `1.0` or `0.0` comes back ok, with that number and with its choice
    unchanged. graph/tests/test_decisions.py and graph/tests/test_provider_jev.py stay green.
  sources:
  - docs/rfc/jev-cuts-brief.md:41
  - docs/rfc/jev-cuts-brief.md:53
contract_seen: 0f2c1efe8c14b9d1
accepted_criteria:
  goal: graph/lib/decisions.py answers a reply whose confidence is Infinity, -Infinity, NaN, 1.5 or -0.1
    with no usable answer — either not ok, or a confidence of None — and answers a reply whose confidence
    is 0.0, 0.6, 0.61 or 1.0 with ok, that same number and its choice unchanged.
  gate: "set -e -o pipefail\ntimeout 600 python3 - <<'PY'\nimport os, pathlib, sys\nroot = pathlib.Path(os.getcwd()).resolve()\n\
    sys.path.insert(0, str(root / \"graph\" / \"lib\"))\nimport decisions\n\nQUESTIONS = {\"cut\": {\"\
    instructions\": \"ask\", \"criteria\": {\"split\": \"a\", \"keep_together\": \"b\"}}}\n\ndef reply(literal):\n\
    \    return ('{\"answers\": {\"cut\": {\"type\": \"choice\", \"choice\": \"keep_together\", '\n  \
    \          '\"confidence\": ' + literal + '}}, \"usage\": {\"cost\": 1e-05}}')\n\ndef asked(literal):\n\
    \    return decisions.ask({\"first\": \"one\", \"second\": \"two\"}, QUESTIONS,\n                \
    \         post=lambda body, text=reply(literal): text)\n\ndef no_usable_answer(got):\n    if not got.ok:\n\
    \        return True\n    one = got.answers.get(\"cut\")\n    return not isinstance(one, dict) or\
    \ one.get(\"confidence\") is None\n\nfor bad in (\"Infinity\", \"-Infinity\", \"NaN\", \"1.5\", \"\
    -0.1\"):\n    got = asked(bad)\n    assert no_usable_answer(got), f\"confidence {bad} came back usable:\
    \ {got}\"\n\nfor good, value in ((\"0.6\", 0.6), (\"0.61\", 0.61), (\"1.0\", 1.0), (\"0.0\", 0.0)):\n\
    \    got = asked(good)\n    assert got.ok, f\"confidence {good} was refused: {got.why}\"\n    assert\
    \ got.answers[\"cut\"] == {\"choice\": \"keep_together\", \"confidence\": value}, got.answers\nprint(\"\
    PROBE OK\")\nPY\n(cd graph/tests && timeout 600 python3 -m unittest test_decisions)\n(cd graph/tests\
    \ && timeout 600 python3 -m unittest test_provider_jev)"
  done_when: The gate passes. Through `ask()` with a stubbed `post`, a reply whose confidence is `Infinity`,
    `-Infinity`, `NaN`, `1.5` or `-0.1` comes back either not ok or with its confidence `None`. A reply
    whose confidence is `0.6`, `0.61`, `1.0` or `0.0` comes back ok, with that number and with its choice
    unchanged. graph/tests/test_decisions.py and graph/tests/test_provider_jev.py stay green.
  files:
  - graph/lib/decisions.py
rebuild_from: /var/tmp/graph-trees/graph-513ubv_t/task-decisions-confidence-is-finite
session: c1c8f06d-fcd8-4591-8882-38d29eaff625
session_account: personal

commit: 100cd7000a8f2f7b2852eed53ac698adc8f01c24
worktree: /var/tmp/graph-trees/graph-513ubv_t/task-decisions-confidence-is-finite
kept_at: '2026-09-20T17:55:31Z'
---

## Goal

graph/lib/decisions.py answers a reply whose confidence is Infinity, -Infinity, NaN, 1.5 or -0.1 with no usable answer — either not ok, or a confidence of None — and answers a reply whose confidence is 0.0, 0.6, 0.61 or 1.0 with ok, that same number and its choice unchanged.

## Why

The brief makes a verdict usable only at or above the 0.6 gate. `provider_jev._number` accepts any float, so a reply saying `Infinity`, `NaN` or `1.5` is read as a confidence and clears that gate — a molecule could be merged on a number that is not a probability.

## Done when

The gate passes. Through `ask()` with a stubbed `post`, a reply whose confidence is `Infinity`, `-Infinity`, `NaN`, `1.5` or `-0.1` comes back either not ok or with its confidence `None`. A reply whose confidence is `0.6`, `0.61`, `1.0` or `0.0` comes back ok, with that number and with its choice unchanged. graph/tests/test_decisions.py and graph/tests/test_provider_jev.py stay green.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, sys
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
import decisions

QUESTIONS = {"cut": {"instructions": "ask", "criteria": {"split": "a", "keep_together": "b"}}}

def reply(literal):
    return ('{"answers": {"cut": {"type": "choice", "choice": "keep_together", '
            '"confidence": ' + literal + '}}, "usage": {"cost": 1e-05}}')

def asked(literal):
    return decisions.ask({"first": "one", "second": "two"}, QUESTIONS,
                         post=lambda body, text=reply(literal): text)

def no_usable_answer(got):
    if not got.ok:
        return True
    one = got.answers.get("cut")
    return not isinstance(one, dict) or one.get("confidence") is None

for bad in ("Infinity", "-Infinity", "NaN", "1.5", "-0.1"):
    got = asked(bad)
    assert no_usable_answer(got), f"confidence {bad} came back usable: {got}"

for good, value in (("0.6", 0.6), ("0.61", 0.61), ("1.0", 1.0), ("0.0", 0.0)):
    got = asked(good)
    assert got.ok, f"confidence {good} was refused: {got.why}"
    assert got.answers["cut"] == {"choice": "keep_together", "confidence": value}, got.answers
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_decisions)
(cd graph/tests && timeout 600 python3 -m unittest test_provider_jev)
```

## Note

Red today: the probe fails with `confidence Infinity came back usable`, `ask` returning `ok=True` and `confidence=inf`. `NaN`, `1.5` and `-0.1` are read the same way. graph/lib/provider_jev.py keeps its present behaviour and is not in the file list, so `_number` stays as it is. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the file listed.
