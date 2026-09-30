# 10: the builder may run the interpreter the gate runs by its full path

## What the owner wants

A project profile can name its interpreter by full path in its `suite_command`, as the guide advises for
a scrubbed gate environment (for example a virtual environment's `python`). The builder is then
granted `Bash(python *)`, because `gate_programs.programs()` keeps only the file name. Claude Code
matches a command as it is written, so the builder's own command, which starts with the full path, is
denied under `--permission-mode dontAsk`: the builder can run neither its own tests nor helpers, and a
repair round then changes nothing and the run stops. This is issue #220, graded `P2`; the owner asked
on 30 September 2026 that the loop build it.

## What changes

- **`code_shell` names a program as the gate spelled it.** In `graph/lib/code_grant.py`, for each program
  the gate runs that the gate spelled with a slash (an absolute path like `/venv/bin/python`, or a relative
  one like `./run.sh`), the grant also holds `Bash(<that spelling> *)`, beside the bare-name grant it
  holds today. A program spelled without a slash is granted exactly as today.
- **Safe spellings only.** A spelling is granted only when it is made of letters, digits and the
  characters `_ . / + -`, so a path with a space, a quote, `$` or any other syntax is not granted in its
  path form (its bare-name grant stays as today).
- **The floor stays.** `NEVER_WILDCARD` is judged on the bare name: a program on it gets no grant in either
  spelling, whatever path it was written with.
- **Nothing else moves.** `gate_programs.programs()` still returns bare names in the order it does, and
  its other readers (`graph/lib/provider_words.py` and any other) see no change; the denies are untouched.

## Edges

- The same path written twice in a gate is granted once; a path and its bare name are two grants.
- A `VAR=value` prefix, a command substitution and a heredoc body are read exactly as the program reader
  reads them today.
- A gate the reader cannot parse still yields nothing, and the builder gets the fixed base alone.
- Every Python file stays at or under 200 lines.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. A gate whose first command is `/venv/bin/python tests/run.py` grants `Bash(python *)` and
   `Bash(/venv/bin/python *)`.
2. A gate that runs `./run.sh` grants `Bash(run.sh *)` and `Bash(./run.sh *)`.
3. A gate that names a program by a path with a space, a quote or `$` grants only its bare-name form, as
   today.
4. A `NEVER_WILDCARD` program written by path (for example `/bin/bash`) gets no grant in either form.
5. A gate with only bare names grants exactly what it did before this change, in the same order.
6. `programs()` returns the same list as before for each of these gates.
7. Every earlier test still passes. The builder may change any earlier test that pins the exact grant
   string of a gate that spells a program with a slash, and nothing else in them. The builder adds new test
   files as the checks above need.

## Out of scope

The rule that drops a project's own `permissions.allow` entries in an untrusted worktree, the other open
issues (#223, #224, #234), and any change to which programs are never granted.
