---
files:
- graph/lib/cuts_command.py
- graph/lib/cli_args.py
- graph/graph-goal.py
- graph/tests/test_cuts_command.py
gate_files_are_the_work: true
may_add_files: true
status: done
requirement:
  goal: 'Create graph/lib/cuts_command.py with command_cuts(args). It resolves the campaign root as Workspace(args.workspace
    or where.campaign()).root, the way graph_commands._space does, without importing that private helper.
    With args.state set it calls cut_states.switch(root, args.state, args.by) and prints the new state.
    With args.state None it prints cut_states.load(root) and then one line per history entry showing to,
    by and at. With a state but no by it prints a message to stderr and returns 2 without writing anything.
    Register a `cuts` subparser in graph/lib/cli_args.py, with --state (choices off, observe, act; default
    None) and --by (string; default empty), and add "cuts": command_cuts to the commands dict in graph/graph-goal.py.'
  done_when: The test builds a parser with cli_args.build_parser and parses `--workspace <tmp> cuts --state
    act --by NAME`. Running args.run(args) writes <tmp>/cut-states.yaml with state act and one history
    entry carrying to and by. A following bare `cuts` prints the state and that entry. A state given without
    --by returns 2 and leaves the file unchanged. The parser rejects a state outside off, observe and
    act.
  sources: []
contract_seen: 7bbc511d7878c6fd
accepted_criteria:
  goal: 'Create graph/lib/cuts_command.py with command_cuts(args). It resolves the campaign root as Workspace(args.workspace
    or where.campaign()).root, the way graph_commands._space does, without importing that private helper.
    With args.state set it calls cut_states.switch(root, args.state, args.by) and prints the new state.
    With args.state None it prints cut_states.load(root) and then one line per history entry showing to,
    by and at. With a state but no by it prints a message to stderr and returns 2 without writing anything.
    Register a `cuts` subparser in graph/lib/cli_args.py, with --state (choices off, observe, act; default
    None) and --by (string; default empty), and add "cuts": command_cuts to the commands dict in graph/graph-goal.py.'
  gate: 'set -e -o pipefail

    (cd graph/tests && timeout 600 python3 -m unittest test_cuts_command)

    '
  done_when: The test builds a parser with cli_args.build_parser and parses `--workspace <tmp> cuts --state
    act --by NAME`. Running args.run(args) writes <tmp>/cut-states.yaml with state act and one history
    entry carrying to and by. A following bare `cuts` prints the state and that entry. A state given without
    --by returns 2 and leaves the file unchanged. The parser rejects a state outside off, observe and
    act.
  files:
  - graph/graph-goal.py
  - graph/lib/cli_args.py
  - graph/lib/cuts_command.py
  - graph/tests/test_cuts_command.py
rebuild_from: /var/tmp/graph-trees/graph-y38nm38g/task-cuts-command.cuts-subcommand
session: 98a96db6-c258-4b4c-a6ae-912efb9cb5df
session_account: personal

commit: 1f26407e01378c37d14213ad8ac5293758f5fd93
worktree: /var/tmp/graph-trees/graph-y38nm38g/task-cuts-command.cuts-subcommand
kept_at: '2026-09-20T16:31:10Z'
---

## Goal

Create graph/lib/cuts_command.py with command_cuts(args). It resolves the campaign root as Workspace(args.workspace or where.campaign()).root, the way graph_commands._space does, without importing that private helper. With args.state set it calls cut_states.switch(root, args.state, args.by) and prints the new state. With args.state None it prints cut_states.load(root) and then one line per history entry showing to, by and at. With a state but no by it prints a message to stderr and returns 2 without writing anything. Register a `cuts` subparser in graph/lib/cli_args.py, with --state (choices off, observe, act; default None) and --by (string; default empty), and add "cuts": command_cuts to the commands dict in graph/graph-goal.py.

## Done when

The test builds a parser with cli_args.build_parser and parses `--workspace <tmp> cuts --state act --by NAME`. Running args.run(args) writes <tmp>/cut-states.yaml with state act and one history entry carrying to and by. A following bare `cuts` prints the state and that entry. A state given without --by returns 2 and leaves the file unchanged. The parser rejects a state outside off, observe and act.

## Gate

```sh
set -e -o pipefail
(cd graph/tests && timeout 600 python3 -m unittest test_cuts_command)

```

## Needs

- [[cut-states/01-cut-states-module]]

## Note

cuts_command.py goes in a new file because graph/graph_commands.py is already near the 200-line cap. It imports `from cut_states import load, switch` after putting the repository's slicer directory on sys.path (pathlib.Path(__file__).resolve().parents[2] / "slicer"). Nothing under graph/ imports from slicer/ today. This is a new import direction, chosen because the brief puts the state module in slicer/ and the command in graph-goal.py. The test file declares EXPECTED_TESTS = N like its neighbours, sets sys.path the way graph/tests/test_graph_commands_status.py does, and makes its workspace with Workspace(tempfile.mkdtemp()).init(goal="g", backlog=<temp yaml>) as that file does. The test never touches the network and adds no space.event, because the brief grants none. It does not touch the slicer or the report.
