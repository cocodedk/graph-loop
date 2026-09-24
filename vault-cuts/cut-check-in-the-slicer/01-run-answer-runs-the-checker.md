---
files:
- slicer/slicer_answer.py
- slicer/tests/test_slicer_cut_check.py
may_add_files: true
gate_files_are_the_work: true
status: done
requirement:
  goal: In slicer/slicer_answer.py add an optional keyword `checker` to run_answer, default None. With
    None, behaviour is unchanged. Otherwise, after validate returns a MOLECULE and before any review call,
    call checker(molecule). It returns an object with `molecule` and `findings`. If findings is non-empty,
    raise ValueError joining them, which the existing repair round in slicer.py already feeds back to
    the planner. If the returned molecule differs from the input, validate it again with the same arguments
    and use the result for the review and for publishing. Trace one event, `cut_checked`, with the finding
    count and whether the molecule changed. A checker that raises changes nothing.
  done_when: With a scripted checker, a non-empty findings list makes run_answer raise ValueError before
    the reviewer is called. A checker that returns a changed molecule has that molecule validated again
    and reviewed, and a changed molecule the validator refuses raises ValueError. A checker that raises
    leaves the molecule to go to review as it is. With checker=None the reviewer sees exactly what it
    saw before, and the existing test_slicer tests still pass.
  sources: []
contract_seen: f6511ac2014196d4
accepted_criteria:
  goal: In slicer/slicer_answer.py add an optional keyword `checker` to run_answer, default None. With
    None, behaviour is unchanged. Otherwise, after validate returns a MOLECULE and before any review call,
    call checker(molecule). It returns an object with `molecule` and `findings`. If findings is non-empty,
    raise ValueError joining them, which the existing repair round in slicer.py already feeds back to
    the planner. If the returned molecule differs from the input, validate it again with the same arguments
    and use the result for the review and for publishing. Trace one event, `cut_checked`, with the finding
    count and whether the molecule changed. A checker that raises changes nothing.
  gate: 'set -e -o pipefail

    (cd slicer/tests && timeout 600 python3 -m unittest test_slicer_cut_check)

    (cd slicer/tests && timeout 600 python3 -m unittest test_slicer)

    '
  done_when: With a scripted checker, a non-empty findings list makes run_answer raise ValueError before
    the reviewer is called. A checker that returns a changed molecule has that molecule validated again
    and reviewed, and a changed molecule the validator refuses raises ValueError. A checker that raises
    leaves the molecule to go to review as it is. With checker=None the reviewer sees exactly what it
    saw before, and the existing test_slicer tests still pass.
  files:
  - slicer/slicer_answer.py
  - slicer/tests/test_slicer_cut_check.py
rebuild_from: /var/tmp/graph-trees/graph-3a5tfkra/task-cut-check-in-the-slicer.run-answer-runs-the-checker
session: 8fc44da8-da76-45b3-94d4-a6e78aaa52ca
session_account: personal
rebuild_round: 2
rejections:
- 'Diff line 33 (goal): Passing the original mutable molecule to the checker allows mutations to survive
  exceptions and bypass revalidation. — A scripted checker that sets molecule[''goal''] then raises RuntimeError
  leaves the changed goal in the returned answer, violating ''A checker that raises changes nothing.''
  A checker that sets molecule[''files'']=''not a list'' and returns that same molecule with empty findings
  produces changed=False and zero revalidation calls. The invalid molecule then proceeds toward review
  and publishing.'
- 'Diff line 26 (goal): The truthiness guard skips valid callable checkers that evaluate to false. The
  contract disables checking only when checker is None. — A scripted callable with __bool__ returning
  False and __call__ returning findings=[''reject this cut''] was never called; run_answer instead called
  the reviewer and publisher once each and returned published. Use `if checker is not None:`.'

commit: 34ac7f77653fc43fa3a605b2a35e6d4d65bfaa48
worktree: /var/tmp/graph-trees/graph-3a5tfkra/task-cut-check-in-the-slicer.run-answer-runs-the-checker
kept_at: '2026-09-20T16:38:25Z'
---

## Goal

In slicer/slicer_answer.py add an optional keyword `checker` to run_answer, default None. With None, behaviour is unchanged. Otherwise, after validate returns a MOLECULE and before any review call, call checker(molecule). It returns an object with `molecule` and `findings`. If findings is non-empty, raise ValueError joining them, which the existing repair round in slicer.py already feeds back to the planner. If the returned molecule differs from the input, validate it again with the same arguments and use the result for the review and for publishing. Trace one event, `cut_checked`, with the finding count and whether the molecule changed. A checker that raises changes nothing.

## Done when

With a scripted checker, a non-empty findings list makes run_answer raise ValueError before the reviewer is called. A checker that returns a changed molecule has that molecule validated again and reviewed, and a changed molecule the validator refuses raises ValueError. A checker that raises leaves the molecule to go to review as it is. With checker=None the reviewer sees exactly what it saw before, and the existing test_slicer tests still pass.

## Gate

```sh
set -e -o pipefail
(cd slicer/tests && timeout 600 python3 -m unittest test_slicer_cut_check)
(cd slicer/tests && timeout 600 python3 -m unittest test_slicer)

```

## Needs

- [[cut-check/molecule]]

## Note

slicer/slicer_answer.py is edited and slicer/tests/test_slicer_cut_check.py is new. The test injects a scripted reviewer and scripted checkers and uses no network. It needs no fixture shape from outside the repository. Build the molecule dict and the repo fixture the way slicer/tests/test_slicer.py does.
