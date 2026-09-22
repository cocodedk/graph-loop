"""What the slicer asks: the planner's prompt and both review prompts.

Split from `slicer.py` at the 200-line cap."""

from __future__ import annotations

import pathlib

import yaml  # type: ignore[import-untyped]
from asking_lists import (  # noqa: F401 — asking stays the one door
    CONTRACT,
    PROMPT_BUDGET,
    contract_text,
    contracts_shown,
    index,
    replacements,
)
from review_scope import (
    VERDICT,  # type: ignore[import-not-found]  # graph/lib, on the path
)
from slicer_law import lineage
from slicer_state import files


def prompt(repo: pathlib.Path, sources: list[pathlib.Path], rows: list[dict],
           target: dict | None = None, evidence: list[pathlib.Path] | None = None) -> str:
    relative = [str(path.resolve().relative_to(repo.resolve())) for path in sources]
    # A real path out of this repository, never a `repo/path:line` template: shown
    # one, a planner wrote the word `repo/` into the anchor and spent two of its
    # three rounds getting it back out (2026-09-18).
    spelled = [str(path.resolve().relative_to(repo.resolve())) for path in files(sources)]
    anchor = f"{spelled[0]}:1" if spelled else "an approved source path, then :1"
    task = yaml.safe_dump(target, sort_keys=False) if target else "none — find the next uncovered claim"
    # a wall's ancestors are prior art the planner must not repeat (SLICER.md:
    # "for a wall it also reads the target, its ancestors, every recorded
    # finding")
    family = lineage(target, rows)[1:] if target else []
    ancestry = yaml.safe_dump(family, sort_keys=False) if family else "none"
    return (
        "Read the approved sources AND the code before planning. Emit the smallest buildable "
        "CODE molecule. One idea, one gate per atom, dependencies only when real. Every name "
        "in uses/creates is path:text, like `src/main/Link.java:parseLink` — the file AND the text in it. A "
        "bare path is not a name and neither is `creates: [result.txt]`, so omit creates when no exact text is "
        "needed. Those two fields are the only names: every entry in files is a bare repository path and "
        "never `path:text`, because it is write authority and the builder is fenced to exactly it. Never invent LIVE authority. Before answering, try to pass each gate without doing its work: "
        "close that route, make it fail today for the intended reason, and claim in goal and done_when only "
        "what it proves. Never invent a required method, and never invent the SHAPE of data from outside "
        "this repository — a page, a response, a file format: if no approved source or existing file "
        "declares it, a fixture you write is that invention with a path on it. Put file boundaries in "
        "note; if an approved source requires a method the gate cannot observe, or a shape nothing here "
        "declares, answer NEEDS_PERSON.\n\n"
        "Repository: the directory you are running in, a throwaway copy of the campaign "
        "tip. Never write its path: the builder runs the gate in its own worktree "
        "elsewhere, and this copy is deleted before any builder starts, so every path "
        "in a card is relative.\n"
        "Target worktree/rebuild_from paths and attempt diffs are unlanded builder work, "
        "not proof of completion. Read the campaign tip here to decide what is already complete; "
        "never use an attempt worktree as the repository baseline.\n"
        f"Approved sources: {relative}\n"
        "Existing molecules, one line each (already covered — never plan their work again):\n"
        f"{index(rows) if rows else 'none'}\n"
        f"Target leaf:\n{task}\n"
        + ("Its `refused_why` and `replan_history` are sentences recorded when a REWRITE of "
           "that one card was refused. A rewrite may not add a file, and they say so; you are "
           "not writing one, and that is not this layer's law. A molecule of two or more atoms "
           "MAY grant a file the target never held — put the source work in a prerequisite atom "
           "at an earlier stage and the gate that proves it in a later one. Never conclude from "
           "a recorded sentence that widening the grant is forbidden here.\n" if target else "")
        +
        f"Ancestors of the target, nearest first (prior art, never to repeat):\n{ancestry}\n"
        f"Extra failure evidence paths: {[str(path) for path in evidence or []]}\n\n"
        "Answer with YAML only. Exact top keys: result, reason, molecule. result is "
        "MOLECULE, NO_GAP or NEEDS_PERSON. For MOLECULE, molecule requires name, source "
        "(anchors, each an approved source path spelled exactly as listed above followed by "
        f"ONE existing line number, like `{anchor}` — never a range "
        "like :13-17, never a whole file), goal, why, needs and atoms. Its name is new and "
        "unequal to every existing task id. source may cite only the approved sources above, "
        "never code or failure evidence. An empty atoms list makes the molecule itself "
        "runnable and also requires files, gate and done_when. Otherwise each "
        "atom requires name, stage, goal, files, gate and done_when. stage is a positive integer "
        "such as 1, never a word; note, needs, uses, creates "
        "and existing gate flags are optional. If an atom's gate runs one of its own "
        "test files, it must say gate_files_are_the_work: true, or leave that file out "
        "of files. A gate must never hide or delete the output a builder needs "
        "(no quiet flags that drop compiler errors, no deleting the log it greps). "
        "A stub's acceptance checks compilation/interface availability, never continued non-implementation. "
        "For a red-first judge (or a temporary probe asserting absence), write gate_until_kept: true "
        "and gate_when_kept: the explicit lasting shell check that requires the same test to PASS. "
        "After the card is done only gate_when_kept is repeated; shell is never inverted automatically. "
        "A gate's own output goes to `$(mktemp)` or under `$TMPDIR`, never a file "
        "inside the repository and never a path under the host's own /tmp. A gate's first line must be exactly `set -e -o pipefail`, never joined "
        "to the rest with `;`, or a later step can pass while an earlier one failed. Never pin "
        "EXPECTED to a literal, to len(...), or to a value read from HEAD: the runner's "
        "EXPECTED counts test cases and moves as tests land, so assert it only against what "
        "the runner collects (`countTestCases()`/`run_all.EXPECTED`). A task "
        "creating a file that is absent now sets "
        "may_add_files: true. The loop supplies ids and statuses.")


def coverage_prompt(repo: pathlib.Path, sources: list[pathlib.Path], rows: list[dict]) -> str:
    body = []
    for source in files(sources):
        body.append(f"--- {source.relative_to(repo)} ---\n{source.read_text('utf-8')}")
    # Settled is not proof, and it holds three different things: a card that is
    # done, one that was dropped, and a parent whose pieces are settled. Only
    # the first has a gate that passed. The other two are listed in full, in two
    # sections because each is judged differently — and each is sized against
    # the budget on its own, as the roster is.
    judged = [row for row in rows if row.get("status") not in ("done", "sliced")]
    replaced = [row for row in rows if row.get("status") == "sliced"]
    return (
        "Independently review whether every declared acceptance claim below is covered by a "
        "molecule. A contract can judge what exists but not what was omitted. "
        + VERDICT + "\n\n"
        f"Repository to inspect: {repo}\n\n"
        + "\n".join(body)
        + "\n\nEvery molecule, one line each — id, status, files, the goal's first line:\n"
        + index(rows)
        + "\n\nWhat the statuses mean. `done`: its gate passed on the branch, so its claim "
          "is proven. `dropped`: the card was decided against and proves nothing, so its "
          "claim is covered only if another molecule carries it. `sliced`: the card was "
          "replaced, and its claim survives only if the molecules that replaced it carry "
          "it — check that they do, never assume it. Anything else is still open, "
          "and is what this review decides.\n"
        "\nThe complete contract of every molecule that is neither done nor sliced:\n"
        + contracts_shown(judged)
        + "\n\nWhat replaced each molecule that was replaced. Read from each piece's own "
          "`sliced_from` and from its id, never from a `needs` list, which holds "
          "prerequisites too:\n"
        + replacements(rows)
        + "\n\nThe complete contract of every molecule that was replaced:\n"
        + contracts_shown(replaced))


def progress_prompt(repo: pathlib.Path, target: dict, made: dict) -> str:
    return (
        "Independently judge this recursive CODE slice before it is published. Accept only "
        "when the replacement removes the recorded blocker and is genuinely narrower or "
        "divides the work. Reject a new id, wording change or swapped gate that leaves the "
        "same breadth or failure. A one-leaf replacement may be semantically narrower; do "
        "not demand a file-count change. " + VERDICT + "\n\n"
        f"Repository to inspect: {repo}\nTarget:\n{yaml.safe_dump(target, sort_keys=False)}\n"
        f"Replacement:\n{yaml.safe_dump(made, sort_keys=False)}")
