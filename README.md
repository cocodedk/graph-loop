# graph-loop

A method for breaking a large body of work into tasks an agent loop can run unattended, and
the design of a loop that runs them.

**What this repository contains:** the loop itself — `drive/`, the driver, and `slicer/`,
the plan phase that writes the cards — plus the method as a Claude Code skill, the design,
and the diary of building and running it.

**What running it requires:** a machine with `python3`, `git`,
`bash` and `ps`, and command-line access to **two different model providers** — one that
builds and one that reviews. That is not incidental. The whole design rests on the reviewer
having blind spots the builder does not, so a single-provider setup is a different tool.

## The idea

Two models that never trust each other. A reviewer refuses any task whose gate could pass
without the work being done. A builder does one task in a private worktree. A gate — a
command whose exit code is the verdict — decides. A fresh reviewer reads the finished diff.
Only then is the work committed.

The backlog is a vault of Obsidian notes inside the repository being built. One note is one
card: what a person reads is byte for byte what the loop reads, `Needs` and `Uses` are
`[[wikilinks]]`, so the graph view is the dependency graph, and the loop writes only the
front matter. Planning and building are separate commands that never overlap.

Everything said, heard and measured is appended to a log, and a watchdog reads that log to
catch the loop going through the motions. A person is needed only where a task says so, and
the loop says out loud when it needs one.

The counter-intuitive part, and the reason it is worth the money: **reviews are 70 to 99
percent of the clock.** One campaign refused nine tasks in a row and built nothing, for
$0.00, and that was the system working. The backlog was the defect. The lever on speed is
better task contracts, not faster builders.

## Install the skill

```
/plugin marketplace add cocodedk/graph-loop
/plugin install drive@graph-loop
```

The skill fires when you are slicing work into tasks for an unattended run, judging whether
a task is ready to hand to a builder, or working out why a backlog stalls. It is useful on
its own — the method does not need the driver.

## Read

- **[docs/DESIGN.md](docs/DESIGN.md)** — the parts, the task contract, the order of one
  task and why each step is where it is. Enough to build the loop yourself.
- **[docs/STATUS.md](docs/STATUS.md)** — where this repository is, what is deliberately missing, and where to pick it up.
- **[docs/DIARY.md](docs/DIARY.md)** — what each rule cost. Every incident is real; none of
  them points at anything real. The numbers are untouched, because they are what makes a
  rule believable.

If you only read one thing, read the diary. The rules are short and sound arbitrary until
you see what buying them cost.

## Run it

```
export DRIVE_REPO=/path/to/the/repository/being/built
export DRIVE_CAMPAIGN=$DRIVE_REPO/scratchpad/campaign

python3 drive/drive-goal.py init --goal "..." --backlog "$DRIVE_REPO/vault" \
                                 --branch campaign/one --source spec/brief.md
python3 drive/drive-goal.py approve       # you have read the goal and the sources
python3 drive/drive-goal.py plan          # write every card, reviewed; build nothing
python3 drive/drive-goal.py run           # build the cards; write none
```

A campaign runs for days, so the thing that actually runs it is `drive/supervisor.sh`, not
the driver: start it and return, then read state from the campaign's log. Never hold a
session open waiting for a campaign to end.

See **[docs/STATUS.md](docs/STATUS.md)** for what is proven and what is not.

## Author

**Babak Bandpey** — [cocode.dk](https://cocode.dk) · [LinkedIn](https://linkedin.com/in/babakbandpey) · [GitHub](https://github.com/cocodedk)

## Licence

MIT | © 2026 [Cocode](https://cocode.dk) | Created by [Babak Bandpey](https://linkedin.com/in/babakbandpey)
