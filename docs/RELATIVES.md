# Relatives: memory and learning around a card

Moved out of `DESIGN.md` when that file passed the 200-line rule. This is the whole
convention and the one command that writes to it; `DESIGN.md` keeps a pointer.

A card is never edited to remember something. What is decided, tried or learned about a
node — a molecule, an atom, a root-level note — goes in a **relative**: a separate note
that links to the node instead. Obsidian then shows the relative as the node's neighbour in
its graph and its backlinks, while the node stays byte for byte what it was, which is what
keeps a card safe to have open while the loop runs.

Three kinds, told apart by the first word of the file name:

| kind | file name | how many | holds |
|---|---|---|---|
| memory | `memory-<node>.md` | one per node, append-only, dated sections | what was decided, tried and measured — it **points to the evidence and never copies it**, so the log stays the one home of the raw record and "nothing is written down twice" stays true |
| learning | `learning-<node>-<slug>.md` | one per learning | front matter `status: open\|adopted\|rejected`, `applies_to`, `basis: measured\|source\|design` |
| evaluation | `evaluation-<scope>.md` | one, written when the project is done | every open learning, read against the logs and marked adopted or rejected; an adopted one becomes a change to the method |

Relatives live in a `relatives/` folder: `<vault>/<Molecule>/relatives/` for a molecule and
its atoms, `<vault>/relatives/` for a root-level note. Never pre-create a molecule folder
to hold one — the slicer renames a finished molecule into place and refuses a name that
already exists.

And never put a relative **beside a card**. `molecule.ordered` reads every `.md` file in a
molecule's folder as an atom except `molecule.md` itself, and a name it cannot read as
`NN-stem.md` stops the whole read — one stray note beside the atoms breaks every card the
picker was about to offer, not just its own. A sub-folder is skipped rather than read as an
atom, which is why relatives live in one.

A relative has a card's shape — front matter, then `## ` sections — so the loop can read it
later without learning a second format.

### `remember`: the memory relative, written from the log

`graph-goal.py remember` is the one thing that writes a relative, and it is a command, not
a step: it is run by hand after a driver has stopped, and nothing on the loop's own path —
`run`, the driver, the supervisor, a hook — reaches it. It reads the campaign's log and the
backlog and writes, for every card, `<backlog>/<Molecule>/relatives/memory-<card>.md`
(`memory-molecule.md` for the molecule itself): front matter `kind: memory` and `node:` a
wikilink the vault resolves, a `## Node` list, then one dated `## ` section per thing that
happened — planned, each attempt with how it ended, each refusal, each gate run with its
exit code and its seconds, the keep with its commit.

It points and never copies. A section carries the event's time, the numbers and the *name*
of the numbered artifact file — `calls/<card>/003-contract-answer.txt` — never the
reviewer's words, never what the gate printed, never the absolute path the log records,
which names the machine the campaign ran on. The log stays the one home of the raw record.

The file a section points at is the one THIS execution wrote. Two things bound an
execution: the window from that card's previous run of the same kind to its next one, and
the `turn` the loop stamps on every event written while one is open. Inside those bounds,
on the side the loop writes it — after the event for a gate's output, before it for an
answer. Never the closest one in the log: a campaign writes one stream and three cards
write into it at once, so distance there is a fact about the other lanes, and it once made
a green gate name the red run's output. A run whose artifact is not in its own bounds
names no file and says the evidence never reached the log — a pointer at a neighbour's
file reads as evidence, which is worse than none.

And a section says what the log says, not what it can guess. `rejected` is the case that
taught it: the loop writes that same event when a diff review finds something, when a
harness retry runs out and when a gate never passes, and nothing in it tells those apart —
so the section says the card was rejected, points at the log by its time, and names no
reviewer and no file.

The note is a projection: the same log gives the same bytes, so running the command twice
writes nothing and a note thrown away is rebuilt exactly. It never touches the card, not
even its front matter, and after it `backlog_tree.read` returns what it returned before.
An event it cannot make sense of is counted and stepped over — the counts are printed —
because a memory note is worth less than the campaign it describes.

**A note is the command's, whole, or it is not the command's at all.** There is no reading
of a person's Markdown, and nothing decides which parts of a file to keep. Four rounds of
review each found another spelling a section scanner read wrong — a heading after a tab, a
heading hidden behind an inline pair of backticks — and each time somebody's text was
deleted. Parsing Markdown by hand to decide what to delete was the defect; a better scanner
was never the fix.

So the note carries a digest of its own body in its own front matter, beside `kind` and
`node`, and a file is the command's to rewrite only when it is byte for byte what the
command last wrote. One edit of any kind, anywhere — a heading, a trailing space, a key of
somebody's own, an emptied file, one byte — and it is a person's: it is kept exactly as it
is and the run reports `kept: edited by hand`. A file that was never the command's, and one
that is not UTF-8 or has no front matter, answer the same question the same way.

Writing beside a card is still a person's to do — in a relative of their own. This one is a
projection of the log and holds nothing that is not in the log, so nothing is lost by its
being rebuilt from scratch every time.

**Nothing is written outside the vault, and nothing through a symlink.** Every path is
resolved, which answers for every ancestor at once — a molecule folder that is itself a
link took both its notes out of the vault before that was asked — and must lie inside the
resolved vault root. A link is refused even when it resolves back inside, because one
pointing at a card would land the write there. That covers the note, its folder and the
`.<name>.tmp` sibling the durable write renames into place.

### What this does not defend against

A hostile local process racing the filesystem during a run. The command resolves every
path, refuses every symlink it can see and creates its temporary file exclusively, so a
link that is there when it looks is never followed. A process that swaps `relatives/` for
a symlink in the milliseconds between that check and the write can still win, and closing
that would mean holding directory handles and writing through `openat` for the whole run.

This is a person's own vault on their own machine, run by hand after a driver has stopped.
A process able to rewrite the vault's folders under it can rewrite the notes directly and
needs no race to do it, so the race buys an attacker nothing they did not already have.
Deliberately not built; say so rather than assume it.

**Nothing in a log can stop the export.** Every line of every part, rotated ones included,
is read inside its own guard: a line that is not a usable JSON object is counted and
stepped over, and the backlog is the first init event that actually names one. No usable
init at all is an answer, printed, not a traceback. Turning one event into a section, and
writing one note, are each guarded the same way.

The loop still does not *read* relatives, and no builder's or reviewer's prompt is fed one.
A card's `status` stays in the card's own front matter, where the loop writes it today.
