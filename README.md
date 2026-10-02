# graph-loop

A loop that builds one feature at a time from a written spec, unattended, and opens a pull
request for a person to merge.

**What this repository contains:** the lean loop (`graph/lean.py`), its dashboard
(`graph/loops.py`), the two Claude Code skills that set it up and watch it, and the writing
that explains what it cost to learn.

**What running it requires:** a machine with `python3`, `git`, `bash` and `ps`, and
command-line access to **two different model providers**: one that builds (`claude`) and one
that reviews (`codex`). That is not incidental. The whole design rests on the reviewer having
blind spots the builder does not, so a single-provider setup is a different tool.

## Website

- [English](https://graph-loop.cocode.dk/)
- [فارسی (Persian)](https://graph-loop.cocode.dk/fa/)

## The idea

Two models that never trust each other. Before anything is built, a reviewer reads the spec
and asks the questions only a person can answer. A builder does the work in a private
worktree off `main`. The project's own suite is the gate. A fresh reviewer reads the finished
diff. Only then is the branch pushed and a pull request opened; `main` never moves, and the
next spec waits until the person has merged the last one.

One spec per run, one run at a time. A red suite or a refused review goes back to the same
builder with the failure text, twice; after that the person is emailed why and the work is
kept where it stopped. Everything said, heard and measured is appended to one event log, and
the dashboard reads that log.

This loop replaced an earlier campaign driver that cut work into cards and reviewed each card
before building it. [docs/rfc/lean-loop.md](docs/rfc/lean-loop.md) records what that cost and
why it was replaced; the driver was removed on 2026-10-02. [docs/DIARY.md](docs/DIARY.md) is
what each rule cost, with the numbers.

## Install the skills

```
/plugin marketplace add cocodedk/graph-loop
/plugin install graph@graph-loop
```

`run` sets the loop up on a project and starts it; `dashboard` shows what is built, building
or waiting.

## Run it

```
python3 graph/graph-goal.py --workspace <ws> contact "<email-address>"   # proves the loop can reach you
python3 graph/lean.py --workspace <ws> --repo <repo> --spec docs/lean/01-first.md
```

The run takes hours; start it in the background and read the mail. Exit 0 is a pull request
ready for review, 1 a stop with the reason mailed, 2 questions before building, 3 a branch
waiting to be merged. The `run` skill has the whole setup.

## Author

**Babak Bandpey** — [cocode.dk](https://cocode.dk) · [LinkedIn](https://linkedin.com/in/babakbandpey) · [GitHub](https://github.com/cocodedk)

## Licence

MIT | © 2026 [Cocode](https://cocode.dk) | Created by [Babak Bandpey](https://linkedin.com/in/babakbandpey)
