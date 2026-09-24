---
files:
- slicer/cut_check.py
- slicer/tests/test_cut_check.py
gate_files_are_the_work: true
may_add_files: true
status: done
requirement:
  goal: Create slicer/cut_check.py with Checked(molecule, findings, verdicts) and check(molecule, campaign,
    space, ask, wall=None). ask is an injected callable taking (state, questions) and returning an object
    with ok and answers. check loads the state with cut_states.load(campaign). When it is off, nothing
    is asked and the molecule comes back unchanged with no findings or verdicts. Otherwise it builds the
    questions with cut_questions.for_cuts and for_atoms(molecule, wall), asks each one, and reads the
    answers into verdicts with cut_verdicts.read. In observe the molecule comes back unchanged with the
    verdicts. In act it applies cut_verdicts.merges through apply_merges and returns the findings from
    cut_verdicts.findings. An ask that reports ok false, or raises, contributes no verdicts and changes
    nothing. space is accepted and not interpreted.
  done_when: The tests show four things. With the state off, the scripted ask is never called and the
    molecule is returned unchanged. With observe, the verdicts are returned and the molecule is unchanged.
    With act, a usable keep_together verdict on two atoms that share a file merges them and a usable fail
    verdict yields a finding. A scripted ask that returns ok false or raises leaves the molecule unchanged
    with no verdicts in every state.
  sources: []
contract_seen: 74cb10b72db118e4
accepted_criteria:
  goal: Create slicer/cut_check.py with Checked(molecule, findings, verdicts) and check(molecule, campaign,
    space, ask, wall=None). ask is an injected callable taking (state, questions) and returning an object
    with ok and answers. check loads the state with cut_states.load(campaign). When it is off, nothing
    is asked and the molecule comes back unchanged with no findings or verdicts. Otherwise it builds the
    questions with cut_questions.for_cuts and for_atoms(molecule, wall), asks each one, and reads the
    answers into verdicts with cut_verdicts.read. In observe the molecule comes back unchanged with the
    verdicts. In act it applies cut_verdicts.merges through apply_merges and returns the findings from
    cut_verdicts.findings. An ask that reports ok false, or raises, contributes no verdicts and changes
    nothing. space is accepted and not interpreted.
  gate: 'set -e -o pipefail

    (cd slicer/tests && timeout 600 python3 -m unittest test_cut_check)

    '
  done_when: The tests show four things. With the state off, the scripted ask is never called and the
    molecule is returned unchanged. With observe, the verdicts are returned and the molecule is unchanged.
    With act, a usable keep_together verdict on two atoms that share a file merges them and a usable fail
    verdict yields a finding. A scripted ask that returns ok false or raises leaves the molecule unchanged
    with no verdicts in every state.
  files:
  - slicer/cut_check.py
  - slicer/tests/test_cut_check.py
rebuild_from: /var/tmp/graph-trees/graph-s6jm8ft5/task-cut-check.cut-check-module
session: b039934b-ba5c-4874-98dd-ed1a496ef1ae
session_account: personal
rebuild_round: 1
rejections:
- 'Diff line 44 (goal): In act state, failed asks can still change the returned molecule because apply_merges
  runs even when there are no verdicts or merges. — A direct probe with atom stages [2, 4] and cut_states.load
  returning ''act'' produced stages [1, 2] for both an ask returning ok=False and an ask raising RuntimeError,
  with empty verdicts and findings. cut_verdicts.apply_merges unconditionally renumbers stages even for
  empty pairs. This violates the requirement that failed asks leave the molecule unchanged.'

commit: 3de3dc4466b7c84b24c5c024e36965cbf91d94ac
worktree: /var/tmp/graph-trees/graph-s6jm8ft5/task-cut-check.cut-check-module
kept_at: '2026-09-20T16:34:02Z'
---

## Goal

Create slicer/cut_check.py with Checked(molecule, findings, verdicts) and check(molecule, campaign, space, ask, wall=None). ask is an injected callable taking (state, questions) and returning an object with ok and answers. check loads the state with cut_states.load(campaign). When it is off, nothing is asked and the molecule comes back unchanged with no findings or verdicts. Otherwise it builds the questions with cut_questions.for_cuts and for_atoms(molecule, wall), asks each one, and reads the answers into verdicts with cut_verdicts.read. In observe the molecule comes back unchanged with the verdicts. In act it applies cut_verdicts.merges through apply_merges and returns the findings from cut_verdicts.findings. An ask that reports ok false, or raises, contributes no verdicts and changes nothing. space is accepted and not interpreted.

## Done when

The tests show four things. With the state off, the scripted ask is never called and the molecule is returned unchanged. With observe, the verdicts are returned and the molecule is unchanged. With act, a usable keep_together verdict on two atoms that share a file merges them and a usable fail verdict yields a finding. A scripted ask that returns ok false or raises leaves the molecule unchanged with no verdicts in every state.

## Gate

```sh
set -e -o pipefail
(cd slicer/tests && timeout 600 python3 -m unittest test_cut_check)

```

## Needs

- [[cut-questions/molecule]]
- [[cut-states/molecule]]
- [[cut-verdicts/molecule]]
- [[decisions-door/molecule]]

## Note

Two new files, slicer/cut_check.py and slicer/tests/test_cut_check.py. The tests write a campaign directory under $TMPDIR, use scripted ask callables, and never touch the network. The sibling modules are created by the molecules listed in needs.
