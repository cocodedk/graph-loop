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

**The command owns two things in a memory note, and nothing else in the file.** The first
is the sections it marks: every heading it writes ends with ` — from the log`. Everything
else comes back byte for byte — the text before the first heading, whatever somebody put
under `## Node` besides the link line, and every unmarked section, each at the place in
the file they put it (its index among the sections, which holds because the log only ever
grows at the end). The one thing to know before writing in one by hand: do not end your
own heading with that phrase, or the next run will take the section over as its own.

The second is the front matter of a note **it makes itself**, which gets `kind` and
`node`. That is the whole of it.

**Front matter that is already there is never edited. At all.** Not a line added, not a
key completed. YAML has more valid spellings than a text edit can know about — flow
mappings, blocks indented two spaces, an explicit `...` terminator, anchors, comments —
and three separate attempts to add a missing key safely each broke a valid note in front
of a reviewer. Reading it into a mapping and writing it back is no better: it loses the
order, the quoting and the comments somebody chose, which for a vault that carries a
property set on every note and queries it across the vault is the whole point of the set.
So an existing note's front matter comes back byte for byte, and if it has no `kind` or no
`node` the summary says so and nothing is added.

**Whose note it is, is asked once and conservatively.** A note is this card's to refresh
only when its front matter has no `node` at all — then it is this card's by where it sits
— or when `node` is a string and exactly this card's link. Anything else is somebody
else's: another card's link, a list holding one, a number, front matter that will not
parse. Then **nothing is written at all** and the summary says why. Rebuilding the history
of a note that says it is about a different card is the one mistake no counter makes up
for, and a guard that only looked at strings once let a list straight through.

**When in doubt, it does not write.** Three rounds of review each found a file spelled a
little differently from what the command expected, written anyway, and something lost. So
a note is refreshed only when every line of a short list is true of its raw bytes, and
anything else is left exactly as it is, counted, and named in the summary:

- valid UTF-8, and no byte-order mark;
- LF line endings only, nowhere a carriage return;
- front matter between plain `---` lines — **an existing file is never given any**,
  because without it nothing says whose note it is, and that is how a foreign note was
  once claimed;
- front matter that parses (every way the parser can fail, not only `YAMLError`: an
  impossible date and a bad tag raise `ValueError`), and names this card by the rule
  above;
- every fenced block closed by the fence rule — the closing fence is the same character,
  at least as long, with nothing after it but spaces or tabs. A non-breaking space does
  not close a fence, and a note whose fences are not all closed is not understood.

A `## ` line inside a fenced block is an example, not a heading — not for ownership, not
for splitting sections, not for finding the link under `## Node`. One scanner knows where
code is and everything asks it. A heading may carry up to three spaces before the hashes,
as CommonMark has it; four make it an indented code block.

A note that IS written is assembled from the pieces that were already there — the front
matter's own bytes, the text before the first heading, each kept section — plus the
sections the command owns. Nothing is re-spelled on the way through. The one thing it
normalises is the blank line between two pieces, because without that a section moving
from the end of a file to the middle grows a blank line on every run.

**Nothing is written through a symlink**: not the note, not the `relatives/` folder, not
the temporary sibling the durable write puts beside it — a symlink left at that name once
truncated a card.

**Nothing in a log can stop the export.** Every line of every part, rotated ones included,
is read inside its own guard: a line that is not a usable JSON object is counted and
stepped over, and the backlog is the first init event that actually names one. No usable
init at all is an answer, printed, not a traceback. Turning one event into a section, and
writing one note, are each guarded the same way. Four reviews found four different things
that took a whole export down before the guards moved to where they belong.

The summary is the command's account of itself: how many notes it wrote, how many already
said it, how many it did not write, and one line per card it could not treat as its own.
It never claims to have left something alone while changing it.

The loop still does not *read* relatives, and no builder's or reviewer's prompt is fed one.
A card's `status` stays in the card's own front matter, where the loop writes it today.
