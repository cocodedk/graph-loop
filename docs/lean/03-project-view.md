# 03: one project's specs, each marked, with filters

## What the owner wants

From the list of running loops (spec 02) the person opens one project and sees every spec of that
project with a mark saying whether it is built, being built, waiting for a person, stopped or still
waiting, and can filter by that mark. It is optional and read-only, like the list.

## The command

`python3 graph/loops.py <which> [--only built|open|attention]` prints the project's view once and
exits with status 0. `<which>` is either a **number** from the list that `python3 graph/loops.py`
prints at that moment, or the **path of a project folder** (which need not have a running loop). Its
logic sits in modules under `graph/lib/`, each under the 200-line cap.

A number that is not in the list prints `no loop number N` and exits with status 2. A path that is
not a folder, or a folder without `docs/lean`, prints `not a project with docs/lean: <path>` and exits
with status 2.

## The specs and their marks

The project's specs are the `*.md` files in its `docs/lean/` folder except `lessons.md`, sorted by file
name. For a number, the project folder is that loop's `--repo`. A spec's **name** is its file name
without `.md`, **as `lean_spec.slug` gives it** (a file name with spaces or punctuation shows as its
slug, the name the loop's branch and commits use). A running loop's `--spec` is matched by the same slug. Each spec gets one mark; the first that holds wins:

1. `▶ building`: a running loop (the finder of spec 02) has this project folder as its `--repo` and this
   spec as its `--spec`.
2. `✔ built`: the project's history on `origin/main` (or `main` when there is no `origin/main`; no spec
   is built when neither exists) has a commit subject that starts with `feat(<name>)`. That is what the
   loop's squash merge leaves. It is read with one `git -C <project> log --format=%s <ref>` call for
   the whole project, not one per spec.
3. `✖ stopped`: the spec's front matter has `lean_status: stopped`.
4. `● pr open`: the spec's front matter has `lean_status: pr_open`. The front matter is read with
   `lean_spec.front`.
5. `· waiting`: none of the above.

Built comes before the front matter on purpose: a spec whose pull request merged long ago can still
say `pr_open` in its file, and it must show as built.

## What it prints

```
fits-api  22 specs: 7 built · 1 building · 1 pr open · 13 waiting
  loop: 02f-routes building 12m03s

✔ built     00-openrouter-provider
✔ built     01-parity-judge
▶ building  02f-routes
· waiting   02g-current-org
```

The first line is the project's folder name and the count of its specs, with the counts of each mark
that is not zero, in the order built, building, stopped, pr open, waiting (the order the sample shows;
the numbered list above only says which mark wins). Under it comes one `loop:` line for each loop
running on this project, lowest process id first, `loop: <spec> <step> <time in step>` as spec 02
defines the step and the time; there is none when no loop runs here. Then a blank line and one line
per spec: the mark padded to the longest mark, two spaces, the name. The counts on the first line
always cover every spec, whatever the filter.

## The filters

`--only built` shows the `✔ built` specs. `--only open` shows every spec that is not built.
`--only attention` shows the `✖ stopped` and `● pr open` specs, the ones a person may have to act on.
A filter that matches no spec prints `no specs match`, after the first line and its `loop:` lines. A
project whose `docs/lean` holds no spec prints `no specs` in the same place, with `0 specs` on the first
line, whatever the filter. Any other value for
`--only` is refused with the usage line and status 2.

## When something cannot be read

- If `git` fails or the project is not a git repository, no spec is built: the marks fall through to the
  front matter, and a line `git history unreadable: nothing is marked built` follows the `loop:` lines.
  The exit status stays 0.
- A spec file that cannot be read, or whose front matter does not parse, is treated as having none:
  it is `· waiting` unless built or building. No message, no crash, status 0.

## Done when

The driver's and the slicer's tests pass, and new tests, with no live process, no network and no real
repository outside a temporary folder (the git output and the running loops are passed in or faked),
prove:

1. The five marks and their order of precedence, including a spec that is both built and `pr_open`,
   and one that is both `building` and built.
2. `lessons.md` and files that are not `.md` are not specs; the order is by file name.
3. Built is read from one git call, from `origin/main` and then `main`, and with neither ref nothing
   is built; a commit whose subject only contains `feat(<name>)` later in the line does not count.
4. Both forms of `<which>` and both error messages with their status.
5. The first line's counts (zero counts left out), the `loop:` line with and without a running loop,
   and the aligned lines.
6. Each filter, `no specs match`, `no specs`, and the refused value; two loops on one project, and a
   spec name with spaces or punctuation shown and matched as its slug.
7. Git failing, and an unreadable or unparsable spec file, as above.
8. The command writes nothing; every file stays under the cap.
9. Every earlier test still passes, unchanged. The builder adds new test files as the checks above
   need.

## Out of scope

The live screen, choosing a loop by key, the card loop, and any change to the lean loop itself.
