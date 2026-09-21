---
source:
- docs/rfc/jev-cuts-brief.md:26
- docs/rfc/jev-cuts-brief.md:27
files:
- graph/lib/gate_sandbox.py
status: done
expect_red: the decisions key survived the scrub
requirement:
  goal: graph/lib/gate_sandbox.py's `environment()` returns a mapping with no `OPENROUTER_API_KEY` in
    it and with `PATH` exactly as it stood in `os.environ`.
  done_when: The gate passes. `environment()` called with only `OPENROUTER_API_KEY` and `PATH` in `os.environ`
    returns a mapping with no `OPENROUTER_API_KEY` in it and with `PATH` still `/bin`. graph/tests/test_gate_sandbox.py
    stays green.
  sources:
  - docs/rfc/jev-cuts-brief.md:26
  - docs/rfc/jev-cuts-brief.md:27
contract_seen: fa088ab3ffb1cc08
accepted_criteria:
  goal: graph/lib/gate_sandbox.py's `environment()` returns a mapping with no `OPENROUTER_API_KEY` in
    it and with `PATH` exactly as it stood in `os.environ`.
  gate: "set -e -o pipefail\ntimeout 600 python3 - <<'PY'\nimport os, pathlib, sys, tempfile\nfrom unittest\
    \ import mock\nroot = pathlib.Path(os.getcwd()).resolve()\nsys.path.insert(0, str(root / \"graph\"\
    \ / \"lib\"))\nimport gate_sandbox\n\nhome = tempfile.mkdtemp()\nwith mock.patch.dict(os.environ,\
    \ {\"OPENROUTER_API_KEY\": \"x\", \"PATH\": \"/bin\"}, clear=True):\n    out = gate_sandbox.environment(home)\n\
    assert \"OPENROUTER_API_KEY\" not in out, f\"the decisions key survived the scrub: {sorted(out)}\"\
    \nassert out[\"PATH\"] == \"/bin\", f\"PATH was not left alone: {out.get('PATH')}\"\nprint(\"PROBE\
    \ OK\")\nPY\n(cd graph/tests && timeout 600 python3 -m unittest test_gate_sandbox)"
  done_when: The gate passes. `environment()` called with only `OPENROUTER_API_KEY` and `PATH` in `os.environ`
    returns a mapping with no `OPENROUTER_API_KEY` in it and with `PATH` still `/bin`. graph/tests/test_gate_sandbox.py
    stays green.
  files:
  - graph/lib/gate_sandbox.py
rebuild_from: /var/tmp/graph-trees/graph-__lrzlp0/task-gate-box-drops-the-decisions-key
session: 0dd9a87f-233c-41f0-9599-3380e45fe7d9
session_account: personal

commit: ffde73a57e78d56feb780765737221df988a0dc5
worktree: /var/tmp/graph-trees/graph-__lrzlp0/task-gate-box-drops-the-decisions-key
kept_at: '2026-09-20T17:57:36Z'
---

## Goal

graph/lib/gate_sandbox.py's `environment()` returns a mapping with no `OPENROUTER_API_KEY` in it and with `PATH` exactly as it stood in `os.environ`.

## Why

The brief says no gate may touch the network. `SECRET_PREFIXES` drops the names that carry a credential, and the decisions model's key — the one this campaign introduced — is not among them, so a gate would run with it in its environment.

## Done when

The gate passes. `environment()` called with only `OPENROUTER_API_KEY` and `PATH` in `os.environ` returns a mapping with no `OPENROUTER_API_KEY` in it and with `PATH` still `/bin`. graph/tests/test_gate_sandbox.py stays green.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import os, pathlib, sys, tempfile
from unittest import mock
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
import gate_sandbox

home = tempfile.mkdtemp()
with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "x", "PATH": "/bin"}, clear=True):
    out = gate_sandbox.environment(home)
assert "OPENROUTER_API_KEY" not in out, f"the decisions key survived the scrub: {sorted(out)}"
assert out["PATH"] == "/bin", f"PATH was not left alone: {out.get('PATH')}"
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_gate_sandbox)
```

## Note

Red today: the probe fails with `the decisions key survived the scrub: ['HOME', 'OPENROUTER_API_KEY', 'PATH', 'PYTHONUSERBASE', 'TMPDIR']`. Every code file stays under 200 lines. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the file listed.
