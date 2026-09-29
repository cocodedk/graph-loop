# 05: a `graph:dashboard` skill that opens a project's dashboard

## What the owner wants

A skill in the graph plugin, `graph:dashboard`, so that saying "open the graph-loop dashboard" in any
project shows that project's dashboard, made of the list of running loops (spec 02), the project's
specs with their marks (spec 03) and the live screen (spec 04). It only shows; it never starts, stops
or edits a loop.

## The skill

`plugins/graph/skills/dashboard/SKILL.md`, next to the `graph` and `run` skills, under 80 lines. Its
front matter has `name: dashboard` and a `description` that starts with `Use when` and names the
requests it answers: opening, showing or checking the graph-loop dashboard, and asking which
graph-loop loops are running or which specs of the current project are built. It tells the agent to:

1. **Find graph-loop** the way the `run` skill's section 1 does, and call the checkout `$GL`. If
   `$GL/graph/loops.sh` does not exist, say that this graph-loop checkout predates the dashboard and
   must be updated (`git pull` in `$GL`), and stop.
2. **Find the project**: the top of the git repository the person is in
   (`git rev-parse --show-toplevel`). If the person named another project, use that folder.
3. **Show it once**: run `bash $GL/graph/loops.sh -1 <project>` and put its output in front of the person.
   For "only what is built", "only what needs me" or "only what is left", run
   `python3 $GL/graph/loops.py <project> --only built|attention|open` instead.
4. **Tell the person how to keep it open**: the live screen cannot refresh inside this conversation, so
   they run `bash $GL/graph/loops.sh <project>` in their own terminal (in Claude Code by typing `!`
   before the command). Name its keys: a digit switches loop, `f` filters, `q` quits. Write the
   command with the real paths filled in.
5. **Stay read-only**: it never starts, stops or edits a loop, a spec or a workspace, and if the
   project has no `docs/lean` it says so instead of guessing what the person wants.

## The plugin's version

`plugins/graph/.claude-plugin/plugin.json`'s `version` goes from `0.3.0` to `0.4.0`, because an
installed plugin only updates when its version changes. The `run` skill gains one sentence pointing to
`graph:dashboard` as the way to watch a running loop.

## Done when

The driver's and the slicer's tests pass, and new tests prove:

1. The skill file exists at its path, is under 80 lines, and its front matter parses with
   `name: dashboard` and a `description` starting with `Use when`.
2. Its text names `loops.sh -1`, `loops.py`, `--only`, `git rev-parse --show-toplevel` and the `!`
   prefix, and never the words `kill`, `rm ` or `git push`.
3. Every `graph/` script the skill names exists in the repository.
4. `plugin.json`'s version is `0.4.0` and the `run` skill mentions `graph:dashboard`.
5. Every earlier test still passes, unchanged. The builder adds new test files as the checks above
   need.

## Out of scope

The card loop, any code change to the dashboard, and starting a loop from the skill.
