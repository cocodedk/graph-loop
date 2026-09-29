# Profile: graph-loop, built by its own lean loop

The lean loop reads the first indented line under each heading below.

## suite_command

    bash scripts/scrub-check.sh && (cd slicer/tests && python3 -m unittest discover -q) && (cd graph/tests && python3 -m unittest discover -q)

The scrub check, then the slicer's tests, then the driver's: the same three CI runs, minus the linter.
CI runs `ruff check .` (pinned 0.16.8) on the pull request; a builder cannot run it in the gate.

## build_command

    mkdir -p out && git ls-files -z graph slicer plugins scripts | xargs -0 tar czf out/graph-loop.tgz

There is nothing to compile: the build proves the branch checks out whole, as a source archive.

## artifact

    out/graph-loop.tgz

## account

    personal
