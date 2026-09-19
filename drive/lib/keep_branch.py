"""Which branch a keeper may move.

Split out of `keep.py` to keep it under the file's own size limit; nothing here
knows about a Keeper, only a repository path and a branch name — the same shape
as `keep_gate.py` and `keep_remote.py`.

The destination is configurable (`init --branch`, `DRIVE_BRANCH`) so the loop
can be pointed at other work. Configured with `main`, the keeper's `update-ref`
moved the main line itself, against BLUEPRINT.md ("What it refuses to do: touch
the main branch") and README.md ("Accepted work goes to a campaign branch. Never
main, never force."). A branch some worktree has checked out is refused for a
second reason: moving the ref behind that checkout's back leaves its HEAD and
index describing a commit the tree does not hold.

The name is checked when the keeper is made, so a misconfigured campaign
fails before anything is committed, gated or published — and again right
before the local `update-ref`, because a branch can be checked out in
between. A push does not move the local campaign branch and is not refused on that ground.
"""

from __future__ import annotations

import subprocess

import where

MAIN_LINE = ("main", "master")


def plain(branch: str) -> str:
    """`branch` without a leading `refs/heads/`, and nothing else touched.

    The one reading, because there were five: `split("refs/heads/")[-1]` also
    cut a name that CONTAINS the prefix, so `campaign/refs/heads/fresh` became
    `fresh` — another branch, created by `init`, named on the pending note,
    pushed and moved by the keeper (an independent review).
    """
    return branch.removeprefix("refs/heads/")


def qualified(branch: str) -> str:
    """The full ref of a campaign branch: `refs/heads/<name>`.

    A bare name is not a branch lookup: `git rev-parse campaign/fresh` prefers a
    TAG of that name, so a tag left in the repository sent the keeper, the
    slicer to another commit — and the next task would have
    started from it (an independent review).
    """
    return f"refs/heads/{plain(branch)}"


def resolve(repo: str, branch: str) -> str:
    """The commit this campaign branch points at, or "" when there is no such
    branch.

    Not `rev-parse`: even given the full ref it falls back to a TAG of that
    exact name, so `refs/tags/refs/heads/campaign/fresh` answered for a branch
    nobody had made — the keeper said it existed and the loop bound its
    decision to the tag's commit (an independent review). `show-ref --verify` reads
    the one ref it is handed, or nothing at all.
    """
    return _git(repo, *resolve_argv(branch)).strip()


def resolve_argv(branch: str) -> list[str]:
    """The git call `resolve` makes, for a caller that has a runner of its own.

    The board measures the base through the runner `view` gives it, and asking
    the same question in a second spelling is how the tag got in: it is written
    here once. `for-each-ref` will not do — its pattern also matches a ref UNDER
    the one asked for, so a branch `campaign/drive/x` would answer for a
    `campaign/drive` that is not there.
    """
    return ["show-ref", "--verify", "--hash", qualified(branch)]


def absent_argv(branch: str) -> list[str]:
    """The git call that says whether this branch is simply NOT THERE.

    `show-ref --exists` answers that and only that: exit 2 is "no such ref",
    while a ref git cannot read — malformed, or naming an object that is gone —
    exits 1 or 0, and a repository it cannot open exits 128. Every reading that
    could not tell those apart called a broken branch "not cut yet" (Codex on
    a886094c). It needs git 2.43 or newer; an older one refuses the option and
    the caller keeps its measurement error, which is the safe direction.
    """
    return ["show-ref", "--exists", qualified(branch)]


def _git(repo: str, *args: str) -> str:
    """git's output, or "" when it fails: every question here has a safe
    unknown — a repository with no remote has no declared default branch."""
    done = subprocess.run(("git", "-C", repo, *args), capture_output=True, text=True,
                          check=False)
    return "" if done.returncode else done.stdout


def _default(repo: str) -> str:
    """The repository's own default branch, from `origin/HEAD` — a main line
    that is called neither `main` nor `master` is still a main line."""
    head = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    return head.split("/", 1)[1] if "/" in head else ""


def protected(repo: str) -> set[str]:
    """The branches a keeper may never move: the two conventional names and the
    repository's own declared default.

    One resolver, read here and by the gate fingerprint (`keep_gate._main_line`),
    so the two can never disagree: reading `main` and `master` by name left a
    repository whose default is `trunk` protected as a destination but unwatched
    while the gates ran, and a gate could move it unremarked (Codex, on the first
    version of that check).
    """
    return {*MAIN_LINE, _default(repo)} - {""}


def _checked_out(repo: str) -> set[str]:
    """Every branch a worktree of this repository holds."""
    return {plain(line.split(" ", 1)[1])
            for line in _git(repo, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("branch ")}


def checked_destination(repo: str, branch: str) -> str:
    """`branch` back, or the reason a keeper may not move it.

    Asked again immediately before every move, never trusted from construction
    time: a branch nothing held when the keeper was made can be checked out
    while a card builds.
    """
    name = plain(branch)
    alias = _git(repo, "symbolic-ref", "-q", f"refs/heads/{name}").strip()
    if alias:
        raise RuntimeError(
            f"{name} is a symbolic ref to {alias}: update-ref follows it, so the work "
            "would land on a branch the campaign never named — a campaign branch is a "
            "real branch, never an alias")
    if name in protected(repo):
        raise RuntimeError(
            f"{name} is the main line: accepted work goes to a campaign branch, "
            "never main (BLUEPRINT.md, 'What it refuses to do')")
    if name in _checked_out(repo):
        raise RuntimeError(
            f"{name} is checked out in a worktree: moving it under a live checkout "
            "leaves that tree describing a commit it does not hold")
    return qualified(branch)


def campaign_branch(repo: str, branch: str) -> str:
    """The campaign's branch name, created at HEAD when the repository has not
    got it yet.

    The slicer plans against a clean checkout of this branch's tip, and the
    branch used to appear only with the first keep — so a fresh campaign had no
    tip, the slicer only logged a skip, and every wall stayed assigned to a
    slicer that could never run (astra's round-3 finding 9). Never a move: a
    branch that is already there is that campaign's own history.

    What comes back is the FULL ref, and that is what the campaign records: the
    keeper normalizes the recorded name once more, so only a spelling that
    survives that reading is safe. `refs/heads/refs/heads/fresh` is the full ref
    of a branch called `refs/heads/fresh`; recording the plain name handed the
    keeper `fresh` back and the first keep died three times on a ref nothing had
    created (an independent review). Off and on again, a full ref is itself.

    A directory that is no repository, or a HEAD with no commit behind it, has
    nothing to branch FROM: the campaign is still recorded, and the slicer has
    no tip to plan against — the other half of the same finding. A repository that
    REFUSES the branch is different in kind, and is said out loud.
    """
    name = plain(branch)
    ref = f"refs/heads/{name}"      # not `qualified(name)`: that strips it again
    if resolve(repo, ref):
        return ref
    if not _git(repo, "rev-parse", "--verify", "HEAD").strip():
        return ref
    made = subprocess.run(("git", "-C", repo, "branch", name, "HEAD"),
                          capture_output=True, text=True, check=False)
    if made.returncode:
        raise SystemExit(f"cannot create {name} in {repo}: {made.stderr.strip()[:200]}")
    return ref


def tip_of(space) -> str:
    """The commit this campaign's kept work sits on.

    One reading, used when a request is opened and again before its answer is
    applied: two ways of asking would call every answer stale. Empty when the
    branch is not there yet — nothing has been kept — because a tip that does
    not exist is not a tip that moved.
    """
    branch = next((str(row.get("branch") or "") for row in space.events()
                   if row.get("kind") == "init"), "") or where.branch()
    return resolve(str(where.repo()), branch)
