# Profile: graph-loop, built by its own lean loop

The lean loop reads the first indented line under each heading below.

## suite_command

    bash scripts/scrub-check.sh && (cd slicer/tests && python3 -m unittest discover -q) && (cd graph/tests && python3 -m unittest discover -q)

The scrub check, then the slicer's tests, then the driver's: the same three CI runs, minus the linter,
which `## lint_command` below runs before it.

## lint_command

    uvx ruff@0.16.8 check .

The linter CI runs on the pull request (pinned 0.16.8), run by the loop before the suite: a red
lint is handed to the builder as a repair round, so lint errors no longer reach CI.

## build_command

    mkdir -p out && git archive --format=tar.gz -o out/graph-loop.tgz HEAD

There is nothing to compile: the build proves the branch checks out whole, as an archive of every tracked file.

## artifact

    out/graph-loop.tgz

## account

    personal
