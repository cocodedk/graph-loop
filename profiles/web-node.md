# Profile: a static web game or site, tested with Node

The lean loop reads the first indented line under each of the three headings below.

## suite_command

    node --test

Node 22's built-in runner finds every `*.test.js` file. The suite runs in a sandbox with an empty
home and no network, so tests must not download anything or read files outside the repository.

## build_command

    node --test

There is no build step: the repository itself is the site. The build is the suite, run on main.

## artifact

    index.html

The page to open. Serve the repository root with any static server and open it.
