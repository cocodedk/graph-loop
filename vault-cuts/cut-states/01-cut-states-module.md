---
files:
- slicer/cut_states.py
- slicer/tests/test_cut_states.py
gate_files_are_the_work: true
may_add_files: true
status: done
requirement:
  goal: Create slicer/cut_states.py with load(campaign) and switch(campaign, to, by). The file is <campaign>/cut-states.yaml,
    holding `state` and a `history` list of {to, by, at}. load returns "off", "observe" or "act", and
    returns "off" when the file is absent. switch writes state=to, appends one {to, by, at} entry to history,
    and keeps the earlier entries.
  done_when: The test passes and proves four things. load on a campaign directory with no cut-states.yaml
    returns "off". After switch(campaign, "observe", "someone"), load returns "observe". A second switch
    to "act" makes load return "act", and the yaml file's history holds two entries in order, each with
    the keys to, by and at, and the first entry unchanged. The `at` value is only asserted to be a non-empty
    string.
  sources: []
contract_seen: 63148cba04e328b5
accepted_criteria:
  goal: Create slicer/cut_states.py with load(campaign) and switch(campaign, to, by). The file is <campaign>/cut-states.yaml,
    holding `state` and a `history` list of {to, by, at}. load returns "off", "observe" or "act", and
    returns "off" when the file is absent. switch writes state=to, appends one {to, by, at} entry to history,
    and keeps the earlier entries.
  gate: 'set -e -o pipefail

    (cd slicer/tests && timeout 600 python3 -m unittest test_cut_states)

    '
  done_when: The test passes and proves four things. load on a campaign directory with no cut-states.yaml
    returns "off". After switch(campaign, "observe", "someone"), load returns "observe". A second switch
    to "act" makes load return "act", and the yaml file's history holds two entries in order, each with
    the keys to, by and at, and the first entry unchanged. The `at` value is only asserted to be a non-empty
    string.
  files:
  - slicer/cut_states.py
  - slicer/tests/test_cut_states.py
rebuild_from: /var/tmp/graph-trees/graph-ibgcpkgp/task-cut-states.cut-states-module
session: 88faa3fd-86c2-45f5-8a9a-e9713c2dec68
session_account: personal

requeued: true
commit: 82758461ba8f1e2a1ba83f7dfe1e1f4199c461d8
worktree: /var/tmp/graph-trees/graph-ibgcpkgp/task-cut-states.cut-states-module
kept_at: '2026-09-20T16:27:20Z'
---

## Goal

Create slicer/cut_states.py with load(campaign) and switch(campaign, to, by). The file is <campaign>/cut-states.yaml, holding `state` and a `history` list of {to, by, at}. load returns "off", "observe" or "act", and returns "off" when the file is absent. switch writes state=to, appends one {to, by, at} entry to history, and keeps the earlier entries.

## Done when

The test passes and proves four things. load on a campaign directory with no cut-states.yaml returns "off". After switch(campaign, "observe", "someone"), load returns "observe". A second switch to "act" makes load return "act", and the yaml file's history holds two entries in order, each with the keys to, by and at, and the first entry unchanged. The `at` value is only asserted to be a non-empty string.

## Gate

```sh
set -e -o pipefail
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_states)

```

## Creates

- [[slicer/cut_states.py:load]]
- [[slicer/cut_states.py:switch]]

## Note

Only slicer/cut_states.py and its test change. The first docstring line states the one job, "the three states". PyYAML is the only dependency. `campaign` is a path passed in, so no new GRAPH_* name. Spell `at` as a UTC timestamp the way graph/lib/loop_judge.py does (%Y-%m-%dT%H:%M:%SZ). Write the file the way slicer/slicer_state.py:close does, to a sibling file and then replace. The test imports tmp_root for its effect and makes its campaign directory under $TMPDIR. The module stays under 200 lines. How a value other than the three states is refused is not specified, so the card does not require it.
