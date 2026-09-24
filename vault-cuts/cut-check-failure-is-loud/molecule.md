---
source:
- docs/rfc/jev-cuts-brief.md:70
- docs/rfc/jev-cuts-brief.md:71
files:
- slicer/slicer_answer.py
status: done
expect_red: no trace line names the failure and its reason
requirement:
  goal: When the checker `run_answer` calls raises, slicer/slicer_answer.py still returns a published
    answer, and the backlog's `.slicer-trace.jsonl` holds a line carrying that exception's type name and
    its message.
  done_when: The gate passes. With a checker that raises `RuntimeError("cut-probe-boom")`, `run_answer`
    still returns `("published", ...)`, and the backlog's `.slicer-trace.jsonl` holds a line carrying
    both `RuntimeError` and `cut-probe-boom`. slicer/tests/test_slicer_cut_check.py and slicer/tests/test_slicer.py
    stay green.
  sources:
  - docs/rfc/jev-cuts-brief.md:70
  - docs/rfc/jev-cuts-brief.md:71
contract_seen: a20176b8828e4593
accepted_criteria:
  goal: When the checker `run_answer` calls raises, slicer/slicer_answer.py still returns a published
    answer, and the backlog's `.slicer-trace.jsonl` holds a line carrying that exception's type name and
    its message.
  gate: "set -e -o pipefail\ntimeout 600 python3 - <<'PY'\nimport os, pathlib, sys, tempfile\nroot = pathlib.Path(os.getcwd()).resolve()\n\
    sys.path.insert(0, str(root / \"graph\" / \"lib\"))\nsys.path.insert(0, str(root / \"slicer\"))\n\
    import yaml\nimport slicer\nfrom intelligence import Reply\n\nrepo = pathlib.Path(tempfile.mkdtemp())\n\
    backlog, specs = repo / \"backlog\", repo / \"specs\"\nbacklog.mkdir()\nspecs.mkdir()\n(specs / \"\
    greeting.md\").write_text(\"## Goal\\nReturn a greeting.\\n\", \"utf-8\")\nanswer = {\"result\": \"\
    MOLECULE\", \"reason\": \"one missing function\", \"molecule\": {\n    \"name\": \"greeting\", \"\
    source\": [\"specs/greeting.md:1\"], \"goal\": \"return a greeting\",\n    \"why\": \"the function\
    \ is absent\", \"needs\": [], \"atoms\": [], \"files\": [\"app.py\"],\n    \"gate\": \"set -e -o pipefail\\\
    nfalse\", \"done_when\": \"the greeting test passes\",\n    \"may_add_files\": True}}\n\ndef checker(molecule):\n\
    \    raise RuntimeError(\"cut-probe-boom\")\n\ngot = slicer.run_answer(yaml.safe_dump(answer), repo=repo,\
    \ backlog=backlog,\n                        sources=[specs], reviewer=lambda question: Reply(True,\
    \ \"ok\"),\n                        checker=checker)\nassert got[0] == \"published\", f\"a failed\
    \ checker changed the outcome: {got}\"\nlines = (backlog / \".slicer-trace.jsonl\").read_text(\"utf-8\"\
    ).splitlines()\nnamed = [line for line in lines if \"RuntimeError\" in line and \"cut-probe-boom\"\
    \ in line]\nassert named, \"no trace line names the failure and its reason:\\n\" + \"\\n\".join(lines)\n\
    print(\"PROBE OK\")\nPY\n(cd slicer/tests && timeout 600 python3 -m unittest test_slicer_cut_check)\n\
    (cd slicer/tests && timeout 600 python3 -m unittest test_slicer)"
  done_when: The gate passes. With a checker that raises `RuntimeError("cut-probe-boom")`, `run_answer`
    still returns `("published", ...)`, and the backlog's `.slicer-trace.jsonl` holds a line carrying
    both `RuntimeError` and `cut-probe-boom`. slicer/tests/test_slicer_cut_check.py and slicer/tests/test_slicer.py
    stay green.
  files:
  - slicer/slicer_answer.py
rebuild_from: /var/tmp/graph-trees/graph-_red36rr/task-cut-check-failure-is-loud
session: 0985c7b1-ef0b-4b33-bb7d-975d4210c84a
session_account: personal

commit: d27bf841efdbd67bd6e2d591f877306bd3a40487
worktree: /var/tmp/graph-trees/graph-_red36rr/task-cut-check-failure-is-loud
kept_at: '2026-09-20T17:53:32Z'
---

## Goal

When the checker `run_answer` calls raises, slicer/slicer_answer.py still returns a published answer, and the backlog's `.slicer-trace.jsonl` holds a line carrying that exception's type name and its message.

## Why

The brief says a decisions model that is unavailable, slow or malformed changes nothing and the event says why. Today `_checked` swallows the exception with a bare `except Exception: return answer`, so a cut check that crashes on every molecule leaves no record at all.

## Done when

The gate passes. With a checker that raises `RuntimeError("cut-probe-boom")`, `run_answer` still returns `("published", ...)`, and the backlog's `.slicer-trace.jsonl` holds a line carrying both `RuntimeError` and `cut-probe-boom`. slicer/tests/test_slicer_cut_check.py and slicer/tests/test_slicer.py stay green.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, sys, tempfile
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
sys.path.insert(0, str(root / "slicer"))
import yaml
import slicer
from intelligence import Reply

repo = pathlib.Path(tempfile.mkdtemp())
backlog, specs = repo / "backlog", repo / "specs"
backlog.mkdir()
specs.mkdir()
(specs / "greeting.md").write_text("## Goal\nReturn a greeting.\n", "utf-8")
answer = {"result": "MOLECULE", "reason": "one missing function", "molecule": {
    "name": "greeting", "source": ["specs/greeting.md:1"], "goal": "return a greeting",
    "why": "the function is absent", "needs": [], "atoms": [], "files": ["app.py"],
    "gate": "set -e -o pipefail\nfalse", "done_when": "the greeting test passes",
    "may_add_files": True}}

def checker(molecule):
    raise RuntimeError("cut-probe-boom")

got = slicer.run_answer(yaml.safe_dump(answer), repo=repo, backlog=backlog,
                        sources=[specs], reviewer=lambda question: Reply(True, "ok"),
                        checker=checker)
assert got[0] == "published", f"a failed checker changed the outcome: {got}"
lines = (backlog / ".slicer-trace.jsonl").read_text("utf-8").splitlines()
named = [line for line in lines if "RuntimeError" in line and "cut-probe-boom" in line]
assert named, "no trace line names the failure and its reason:\n" + "\n".join(lines)
print("PROBE OK")
PY
(cd slicer/tests && timeout 600 python3 -m unittest test_slicer_cut_check)
(cd slicer/tests && timeout 600 python3 -m unittest test_slicer)
```

## Note

Red today: the probe fails with `no trace line names the failure and its reason`, the trace holding only `validated` and `published`. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the file listed.
