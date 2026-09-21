---
source:
- docs/rfc/stalls-brief.md:33
- docs/rfc/stalls-brief.md:34
files:
- graph/lib/cooldown.py
- graph/lib/resources.py
may_add_files: true
status: todo
gate_reviewed_first: true
expect_red: a cooldown is not written down, so a restart forgets it
---

## Goal

`cooldown.start(space, account)` records one `cooling` event in the campaign's event log, keyed by the account's credential directory rather than its label, and answers when the cooldown ends. Called again while that cooldown stands it writes no second event and answers the same ending time. `cooldown.cooling(space)` read from a Workspace opened fresh on the same campaign directory — the next driver start — holds that account's credential and not another's, and leaves out a cooldown whose ending time has passed. A `resources.Exhausted` built with those credentials skips every resource on them and no other.

## Why

`resources.Exhausted` is the loop's record of what has run out, and it is built fresh at every call site — `loop_steps`, `review`, `replan` — so it lives for one card's belt walk and nothing more. Every card on a limited account therefore rediscovers the limit by hitting it, and a restart rediscovers it too. The brief asks for one cooldown per account, held by the campaign rather than by a process.

The campaign's own event log is the thing a restart already reads back: `campaign_of.backlog_of` and `campaign_of.branch_of` are the existing examples of a driver learning a fact from it at start. `space.event(kind, **fields)` appends and `space.events()` reads, and `workspace_claims._now()` writes UTC seconds in a format that compares as a string, so an ending time on the event needs no parsing to be checked.

What runs out is the credential and not the label. `resources` already says so where it decides what to skip — two configured names can point at one directory, and a limit on the first leaves the second looking fresh. A cooldown keyed by label would have exactly that hole, so it is keyed by `accounts.home(account)` the way `resources` keys exhaustion. That private helper may take a public name in graph/lib/resources.py if the new module needs to call it.

`resources.Exhausted()` with no argument must go on behaving as it does today: three call sites build it that way, and none of them has a campaign to hand.

How long a cooldown lasts is a policy, not this card's claim: the gate asks only that the ending time is in the future and that a second start does not move it. graph/lib/resources.py is 124 lines, so the seeding fits there and the reading and writing belong in the new file.

## Done when

The gate passes. Over a temporary campaign, `cooldown.start(space, "work")` returns an ending time later than now and the campaign holds exactly one `cooling` event naming `str(accounts.home("work"))`; a second `cooldown.start(space, "work")` returns the same ending time and adds no event. A `Workspace` opened on the same directory answers `cooldown.cooling(...)` with a set holding `str(accounts.home("work"))` and not `str(accounts.home("second"))`. After a `cooling` event for `second` whose ending time is in the past, `cooling` still leaves `second` out. `resources.Exhausted(cooling=cooldown.cooling(fresh))` skips `Resource("claude", "work", "claude-opus-5")` and does not skip `Resource("claude", "second", "claude-opus-5")`, while `resources.Exhausted()` skips neither. graph/tests/test_accounts.py, graph/tests/test_live_accounts.py, graph/tests/test_turn_accounts.py and graph/tests/test_workspace.py stay green. The gate does not prove how long a cooldown lasts, what starts one, or what the driver does while every account is cooling.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import datetime, os, pathlib, sys, tempfile
root = pathlib.Path(os.getcwd()).resolve()
sys.path.insert(0, str(root / "graph" / "lib"))
sys.path.insert(0, str(root / "graph" / "tests"))
import tmp_root  # noqa: F401 — every temp file of this process under one root
try:
    import cooldown
except ImportError:
    sys.exit("a cooldown is not written down, so a restart forgets it: there is no cooldown module")
import accounts
import resources
from workspace import Workspace

RED = "a cooldown is not written down, so a restart forgets it"
NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
WORK, SECOND = str(accounts.home("work")), str(accounts.home("second"))

space = Workspace(tempfile.mkdtemp()).init(goal="a probe", backlog="b.yaml")
until = cooldown.start(space, "work")
assert str(until) > NOW, f"{RED}: the cooldown ends at {until!r}, which is not ahead of {NOW}"
written = [one for one in space.events() if one.get("kind") == "cooling"]
assert [one.get("account") for one in written] == [WORK], \
    f"{RED}: the campaign holds {written}"

again = cooldown.start(space, "work")
assert again == until, f"{RED}: a second start moved the ending to {again!r}"
written = [one for one in space.events() if one.get("kind") == "cooling"]
assert len(written) == 1, f"{RED}: a second start wrote another event: {written}"

# The next driver start: a Workspace that did not write any of this.
fresh = Workspace(space.root)
cooling = cooldown.cooling(fresh)
assert WORK in cooling, f"{RED}: a fresh campaign reads {cooling}"
assert SECOND not in cooling, f"a cooldown reached another account: {cooling}"

fresh.event("cooling", account=SECOND, until="2020-01-01T00:00:00Z")
cooling = cooldown.cooling(Workspace(space.root))
assert SECOND not in cooling, f"a cooldown that has run out is still honoured: {cooling}"

held = resources.Exhausted(cooling=cooling)
assert held.skip(resources.Resource("claude", "work", "claude-opus-5")), \
    f"{RED}: the belt does not skip a cooling account: {cooling}"
assert not held.skip(resources.Resource("claude", "second", "claude-opus-5")), \
    "the belt skips an account that is not cooling"
plain = resources.Exhausted()
assert not plain.skip(resources.Resource("claude", "work", "claude-opus-5")), \
    "a plain Exhausted no longer starts empty"
print("PROBE OK")
PY
(cd graph/tests && timeout 600 python3 -m unittest test_accounts)
(cd graph/tests && timeout 600 python3 -m unittest test_live_accounts)
(cd graph/tests && timeout 600 python3 -m unittest test_turn_accounts)
(cd graph/tests && timeout 600 python3 -m unittest test_workspace)
```

## Note

Red today: the probe exits with `a cooldown is not written down, so a restart forgets it: there is no cooldown module`. `tmp_root` is what gives the probe its two accounts, so the gate reads them from `accounts.home` rather than writing a path down. Every code file stays under 200 lines; graph/lib/resources.py is 124 lines today. PyYAML is the only third-party dependency. No new `GRAPH_*` environment name. `scripts/scrub-check.sh` stays clean. Write only the files listed.
