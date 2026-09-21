---
source:
- docs/rfc/stalls-brief.md:33
- docs/rfc/stalls-brief.md:34
files:
- graph/lib/cooldown.py
- graph/lib/resources.py
may_add_files: true
status: dropped
gate_reviewed_first: true
expect_red: a cooldown is not written down, so a restart forgets it
requirement:
  goal: '`cooldown.start(space, account)` records one `cooling` event in the campaign''s event log, keyed
    by the account''s credential directory rather than its label, and answers when the cooldown ends.
    Called again while that cooldown stands it writes no second event and answers the same ending time.
    `cooldown.cooling(space)` read from a Workspace opened fresh on the same campaign directory — the
    next driver start — holds that account''s credential and not another''s, and leaves out a cooldown
    whose ending time has passed. A `resources.Exhausted` built with those credentials skips every resource
    on them and no other.'
  done_when: The gate passes. Over a temporary campaign, `cooldown.start(space, "work")` returns an ending
    time later than now and the campaign holds exactly one `cooling` event naming `str(accounts.home("work"))`;
    a second `cooldown.start(space, "work")` returns the same ending time and adds no event. A `Workspace`
    opened on the same directory answers `cooldown.cooling(...)` with a set holding `str(accounts.home("work"))`
    and not `str(accounts.home("second"))`. After a `cooling` event for `second` whose ending time is
    in the past, `cooling` still leaves `second` out. `resources.Exhausted(cooling=cooldown.cooling(fresh))`
    skips `Resource("claude", "work", "claude-opus-5")` and does not skip `Resource("claude", "second",
    "claude-opus-5")`, while `resources.Exhausted()` skips neither. graph/tests/test_accounts.py, graph/tests/test_live_accounts.py,
    graph/tests/test_turn_accounts.py and graph/tests/test_workspace.py stay green. The gate does not
    prove how long a cooldown lasts, what starts one, or what the driver does while every account is cooling.
  sources:
  - docs/rfc/stalls-brief.md:33
  - docs/rfc/stalls-brief.md:34
---

## Goal

`cooldown.start(space, account)` records one `cooling` event in the campaign's event log, keyed by the credential directory that `accounts.home(account)` returns when `start` is called. It does not key by the label. The event carries its ending time, and `start` returns that same ending time. Called again while that cooldown stands, through the same label or through any other label that resolves to the same credential directory, and even from a different process, it writes no second event and returns the same ending time. `cooldown.cooling(space)`, read by a separate process that opens the same campaign directory, holds that credential directory and not another's, and leaves out a cooldown whose ending time has passed. A `resources.Exhausted` built with those credentials skips every resource on them, whatever the model, and no resource on any other credential.

## Why

`resources.Exhausted` is the loop's record of what has run out, and it is built fresh at every call site — `loop_steps`, `review`, `replan` — so it lives for one card's belt walk and nothing more. Every card on a limited account therefore rediscovers the limit by hitting it, and a restart rediscovers it too. The brief asks for one cooldown per account, held by the campaign rather than by a process.

The campaign's own event log is the thing a restart already reads back: `campaign_of.backlog_of` and `campaign_of.branch_of` are the existing examples of a driver learning a fact from it at start. `space.event(kind, **fields)` appends and `space.events()` reads, and `workspace_claims._now()` writes UTC seconds in a format that compares as a string, so an ending time on the event needs no parsing to be checked.

What runs out is the credential and not the label. `resources` already says so where it decides what to skip — two configured names can point at one directory, and a limit on the first leaves the second looking fresh. A cooldown keyed by label would have exactly that hole, so it is keyed by `accounts.home(account)` the way `resources` keys exhaustion. That private helper may take a public name in graph/lib/resources.py if the new module needs to call it.

`resources.Exhausted()` with no argument must go on behaving as it does today: three call sites build it that way, and none of them has a campaign to hand.

How long a cooldown lasts is a policy, not this card's claim: the gate asks only that the ending time is in the future and that a second start does not move it. graph/lib/resources.py is 124 lines, so the seeding fits there and the reading and writing belong in the new file.

## Done when

The gate passes.
In one process, over a temporary campaign, `cooldown.start(space, "work")` returns an ending time that parses as a timestamp later than now.
The campaign holds exactly one `cooling` event, and its `account` is `str(accounts.home("work"))`.
The returned ending time, parsed, equals the parsed `until` field of that persisted event. A constant, or a value not written to the log, fails.
A second `start` in the same process returns the same ending time and adds no event.
Alias identity: with `accounts.home` patched so that the label "work-alias" resolves to the same directory as "work", `start(space, "work-alias")` returns the same ending time and adds no event, in this process and in a separate one. `cooling()` holds that directory once.
A separate Python process that opens the same directory sees `str(accounts.home("work"))` in `cooldown.cooling(...)` and not `str(accounts.home("second"))`. That process also calls `start(..., "work")`, gets an ending time equal to the first process's, and adds no event.
After a `cooling` event for `second` whose ending time is in the past, a further separate process leaves `second` out and keeps `work` in.
`resources.Exhausted(cooling=<that set>)` skips three different models on `work`, skips none of three models on `second`, and skips the same three on the alias label. `resources.Exhausted()` skips none of them.
graph/tests/test_accounts.py, graph/tests/test_live_accounts.py, graph/tests/test_turn_accounts.py and graph/tests/test_workspace.py stay green.
The gate proves that a cooldown survives a real restart, that it is keyed by credential directory including across labels that share one, that the returned ending time is the persisted one, that an expired cooldown is dropped, and that the belt skips by credential across models.
It does not prove how long a cooldown lasts, what starts one, or what the driver does while every account is cooling.
It assumes `cooldown` resolves labels through `accounts.home(...)` at call time, so a patch of that attribute takes effect.

## Gate

```sh
set -e -o pipefail
timeout 600 python3 - <<'PY'
import datetime, json, os, pathlib, subprocess, sys, tempfile
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
UTC = datetime.timezone.utc
NOW = datetime.datetime.now(UTC)
WORK, SECOND = str(accounts.home("work")), str(accounts.home("second"))

def parse(value):
    if isinstance(value, datetime.datetime):
        moment = value
    else:
        moment = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)

ALIAS = (
    "_real = accounts.home\n"
    "accounts.home = lambda label, *a, **k: _real('work' if label == 'work-alias' else label, *a, **k)\n"
)
_real_home = accounts.home
def alias_home(label, *a, **k):
    return _real_home("work" if label == "work-alias" else label, *a, **k)

def other_process(body, directory):
    """Run `body` in a fresh interpreter: nothing in memory carries over."""
    prelude = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(root / 'graph' / 'lib')!r})\n"
        f"sys.path.insert(0, {str(root / 'graph' / 'tests')!r})\n"
        "import tmp_root\n"
        "import accounts, cooldown\n"
        "from workspace import Workspace\n"
        + ALIAS +
        f"space = Workspace({str(directory)!r})\n"
    )
    done = subprocess.run([sys.executable, "-c", prelude + body],
                          capture_output=True, text=True, cwd=str(root), timeout=300)
    assert done.returncode == 0, f"{RED}: a second process failed: {done.stderr[-600:]}"
    return json.loads(done.stdout.strip().splitlines()[-1])

def cooling_events(space):
    return [one for one in space.events() if one.get("kind") == "cooling"]

space = Workspace(tempfile.mkdtemp()).init(goal="a probe", backlog="b.yaml")
until = cooldown.start(space, "work")
try:
    until_at = parse(until)
except (ValueError, TypeError):
    sys.exit(f"{RED}: the cooldown answers {until!r}, which is not a timestamp")
assert until_at > NOW, f"{RED}: the cooldown ends at {until!r}, not ahead of {NOW}"
written = cooling_events(space)
assert [one.get("account") for one in written] == [WORK], f"{RED}: the campaign holds {written}"
assert "until" in written[0], f"{RED}: the event carries no ending time: {written[0]}"
assert parse(written[0]["until"]) == until_at, \
    f"{RED}: start answered {until!r} but the log holds {written[0]['until']!r}"
again = cooldown.start(space, "work")
assert parse(again) == until_at, f"{RED}: a second start moved the ending to {again!r}"
assert len(cooling_events(space)) == 1, f"{RED}: a second start wrote another event"

# Two labels, one credential directory: still one cooldown.
accounts.home = alias_home
try:
    via_alias = cooldown.start(space, "work-alias")
    assert parse(via_alias) == until_at, f"{RED}: an alias label got {via_alias!r}, not {until!r}"
    assert len(cooling_events(space)) == 1, f"{RED}: an alias label wrote a second event"
finally:
    accounts.home = _real_home

# The next driver start: a different process that wrote none of this.
seen = other_process(
    "cooling = cooldown.cooling(space)\n"
    "again = cooldown.start(space, 'work')\n"
    "alias = cooldown.start(space, 'work-alias')\n"
    "count = len([o for o in space.events() if o.get('kind') == 'cooling'])\n"
    "print(json.dumps({'cooling': sorted(cooling), 'again': str(again), 'alias': str(alias),"
    " 'count': count}))\n",
    space.root)
assert WORK in seen["cooling"], f"{RED}: a restarted driver reads {seen['cooling']}"
assert SECOND not in seen["cooling"], f"a cooldown reached another account: {seen['cooling']}"
assert seen["cooling"].count(WORK) == 1, f"one credential listed twice: {seen['cooling']}"
assert parse(seen["again"]) == until_at, \
    f"{RED}: a restarted driver answers {seen['again']!r}, not {until!r}"
assert parse(seen["alias"]) == until_at, \
    f"{RED}: a restarted driver answers an alias with {seen['alias']!r}, not {until!r}"
assert seen["count"] == 1, f"{RED}: a start after a restart wrote another event"

# A cooldown whose ending has passed is left out, by a process that never saw it written.
space.event("cooling", account=SECOND, until="2020-01-01T00:00:00Z")
later = other_process(
    "print(json.dumps({'cooling': sorted(cooldown.cooling(space))}))\n", space.root)
assert SECOND not in later["cooling"], f"a cooldown that has run out is still honoured: {later}"
assert WORK in later["cooling"], f"{RED}: the live cooldown vanished: {later}"

cooling = set(later["cooling"])
models = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5-20251001"]
held = resources.Exhausted(cooling=cooling)
accounts.home = alias_home
try:
    for model in models:
        for label in ("work", "work-alias"):
            assert held.skip(resources.Resource("claude", label, model)), \
                f"{RED}: the belt does not skip {model} on cooling account {label}: {cooling}"
        assert not held.skip(resources.Resource("claude", "second", model)), \
            f"the belt skips {model} on an account that is not cooling"
finally:
    accounts.home = _real_home
plain = resources.Exhausted()
for model in models:
    for label in ("work", "second"):
        assert not plain.skip(resources.Resource("claude", label, model)), \
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

Dropped: judged over-engineered. The driver already waits out an outage, and an uncharged retry no longer counts as watchdog progress (611949f); a durable cooldown store adds machinery without removing a stall.
