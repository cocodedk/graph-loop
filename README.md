# drive-loop

A method for breaking a large body of work into tasks an agent loop can run unattended, and
the design of a loop that runs them.

**What this repository contains today:** the method, as a Claude Code skill; the design of
the loop; and the diary of building and running it. **The runtime is not here yet.** It
lands in one piece, from a source that has stopped changing — see *Status* below.

**What running the loop will require, when it lands:** a machine with `python3`, `git`,
`bash` and `ps`, and command-line access to **two different model providers** — one that
builds and one that reviews. That is not incidental. The whole design rests on the reviewer
having blind spots the builder does not, so a single-provider setup is a different tool.

## The idea

Two models that never trust each other. A reviewer refuses any task whose gate could pass
without the work being done. A builder does one task in a private worktree. A gate — a
command whose exit code is the verdict — decides. A fresh reviewer reads the finished diff.
Only then is the work committed.

Everything said, heard and measured is appended to a log, and a watchdog reads that log to
catch the loop going through the motions. A person is needed only where a task says so, and
the loop says out loud when it needs one.

The counter-intuitive part, and the reason it is worth the money: **reviews are 70 to 99
percent of the clock.** One campaign refused nine tasks in a row and built nothing, for
$0.00, and that was the system working. The backlog was the defect. The lever on speed is
better task contracts, not faster builders.

## Install the skill

```
/plugin marketplace add cocodedk/drive-loop
/plugin install drive@drive-loop
```

The skill fires when you are slicing work into tasks for an unattended run, judging whether
a task is ready to hand to a builder, or working out why a backlog stalls. It is useful on
its own — the method does not need the driver.

## Read

- **[docs/DESIGN.md](docs/DESIGN.md)** — the parts, the task contract, the order of one
  task and why each step is where it is. Enough to build the loop yourself.
- **[docs/DIARY.md](docs/DIARY.md)** — what each rule cost. Every incident is real; none of
  them points at anything real. The numbers are untouched, because they are what makes a
  rule believable.

If you only read one thing, read the diary. The rules are short and sound arbitrary until
you see what buying them cost.

## Status

The loop exists and has produced accepted commits, inside private work. It is being lifted
out in two stages, on purpose:

1. **Now:** the design, the diary and the skill. They carry the transferable value and they
   do not drift when someone fixes a bug in the code.
2. **Later:** the runtime, in one move, once the work it currently serves has finished.

Splitting it this way avoids a fork whose *exercised* copy is private and whose *clean*
copy is the one nobody runs. One open design question is being settled in the meantime: a
campaign runs for days, so the front end has to start the supervisor and return, then read
its state from the log — never hold a session open waiting.

## Author

**Babak Bandpey** — [cocode.dk](https://cocode.dk) · [LinkedIn](https://linkedin.com/in/babakbandpey) · [GitHub](https://github.com/cocodedk)

## Licence

MIT | © 2026 [Cocode](https://cocode.dk) | Created by [Babak Bandpey](https://linkedin.com/in/babakbandpey)
