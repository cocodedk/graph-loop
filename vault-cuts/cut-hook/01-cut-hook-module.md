---
files:
- slicer/cut_hook.py
- slicer/tests/test_cut_hook.py
may_add_files: true
gate_files_are_the_work: true
status: done
requirement:
  goal: Create slicer/cut_hook.py with make_checker(campaign, space, ask, wall=None, check=None). It returns
    a callable taking a molecule and returning check(molecule, campaign, space, ask, wall=wall). When
    check is None it imports check from cut_check at call time. It never accepts or refuses a molecule
    itself.
  done_when: make_checker returns a callable that forwards the molecule, campaign, space, ask and wall
    to the injected check and returns its result unchanged, and the tests prove this with a scripted check
    and no network.
  sources: []
contract_seen: 4cb8c27f002bcb93
accepted_criteria:
  goal: Create slicer/cut_hook.py with make_checker(campaign, space, ask, wall=None, check=None). It returns
    a callable taking a molecule and returning check(molecule, campaign, space, ask, wall=wall). When
    check is None it imports check from cut_check at call time. It never accepts or refuses a molecule
    itself.
  gate: 'set -e -o pipefail

    (cd slicer/tests && timeout 600 python3 -m unittest test_cut_hook)

    '
  done_when: make_checker returns a callable that forwards the molecule, campaign, space, ask and wall
    to the injected check and returns its result unchanged, and the tests prove this with a scripted check
    and no network.
  files:
  - slicer/cut_hook.py
  - slicer/tests/test_cut_hook.py
rebuild_from: /var/tmp/graph-trees/graph-k96azacz/task-cut-hook.cut-hook-module
session: db70fed0-72d5-4846-a0ab-ea5512c4aa84
session_account: personal

commit: 4c17bb40865c715c8a35efc783bb7b4fd3a5806e
worktree: /var/tmp/graph-trees/graph-k96azacz/task-cut-hook.cut-hook-module
kept_at: '2026-09-20T16:39:13Z'
---

## Goal

Create slicer/cut_hook.py with make_checker(campaign, space, ask, wall=None, check=None). It returns a callable taking a molecule and returning check(molecule, campaign, space, ask, wall=wall). When check is None it imports check from cut_check at call time. It never accepts or refuses a molecule itself.

## Done when

make_checker returns a callable that forwards the molecule, campaign, space, ask and wall to the injected check and returns its result unchanged, and the tests prove this with a scripted check and no network.

## Gate

```sh
set -e -o pipefail
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_hook)

```

## Needs

- [[cut-check/molecule]]
- [[cut-check-in-the-slicer/molecule]]

## Note

Two new files only. slicer/cut_check.py is created by the cut-check molecule and is not named in uses because it is absent today. The tests always pass a scripted check and never import cut_check.
