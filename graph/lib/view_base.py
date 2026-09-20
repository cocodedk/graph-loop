"""The board's base-branch flag: the loop cuts every worktree from the
campaign's branch, so a base behind this checkout, a measure that failed, or
a base gone after a kept commit is a red flag. Pure functions over rows and
a git runner; `view` supplies both."""

from __future__ import annotations

from keep_branch import absent_argv, resolve_argv


def recorded_branch(rows: list[dict], fallback: str) -> str:
    """The branch the campaign was started on (`init --branch`), which is the
    one the driver cuts worktrees from; the environment's default otherwise."""
    for row in rows:
        if row.get("kind") == "init":
            return str(row.get("branch") or fallback)
    return fallback

def has_kept_commit(rows: list[dict]) -> bool:
    """Whether the campaign has kept work ON the base: an acceptance that
    carries a commit. An acceptance without one (verified from the record,
    nothing to keep) proves no branch exists."""
    return any(row.get("kind") == "accepted" and row.get("commit") for row in rows)



def base_measure(base: str, run, established: bool = False) -> str:
    """Measure the base with `run(argv) -> (rc, stdout, stderr)` and say what
    the board should: a branch git can look for and does not find is one not cut
    yet — no flag before the campaign's first keep, a red flag after it (the
    keeper would fall back to HEAD and the next task would lose the accepted
    work); a ref git cannot read, and a repository it cannot open, are failed
    measures and red flags either way, as are words on stderr from a read that
    otherwise worked, and anything but one non-negative integer as the count."""
    # The branch itself, read the one way that cannot answer with something
    # else: `rev-parse` falls back to a tag of that name — even of the full
    # ref's name — and said nothing was wrong while the branch the keeper needs
    # was gone (an independent review). One reading, `keep_branch.resolve_argv`.
    rc, out, err = run(resolve_argv(base))
    if rc != 0:
        # `show-ref --verify` says "no such ref", "I cannot read this ref" and
        # "this is not a repository" the same way — exit 128 with words — so
        # which it was is asked, and only "the ref is not there" (exit 2) is an
        # answer about the branch. Asking whether the REPOSITORY was readable
        # instead called a corrupt ref a branch not cut yet.
        absent, _, _ = run(absent_argv(base))
        if absent == 2:
            return (f"  !! the loop's base {base} is GONE though the campaign has kept work "
                    "on it — restore it before the next task is cut from HEAD") \
                if established else ""
        return base_behind(None, base, error=err.strip() or f"git show-ref exited {rc}")
    if err.strip() or not out.strip():
        return base_behind(None, base, error=err.strip() or "git show-ref said nothing")
    # counted FROM the commit just resolved, never from the name again
    rc, out, err = run(["rev-list", "--count", f"{out.strip()}..HEAD"])
    if rc != 0 or err.strip() or not out.strip().isdigit():
        return base_behind(None, base, error=err.strip() or f"git rev-list exited {rc}, said {out.strip()!r}")
    return base_behind(int(out.strip()), base)

def base_behind(count: int | None, base: str, error: str = "") -> str:
    """The loop cuts every worktree from `base`; a base behind this checkout
    runs old gates and an old helper there (two live tasks were quarantined on
    "No such file" for the gate script the checkout already had). A measure
    that failed is a flag too — green by not looking is not green."""
    if error or count is None:
        return f"  !! could not measure the loop's base {base}: {error or 'git gave no count'}"
    if count <= 0:
        return ""
    return (f"  !! the loop's base {base} is {count} commits behind this checkout — "
            f"`git push . HEAD:{base}` (merge its keeps into this checkout first if that is "
            "refused) or the worktrees run old gates and helpers")
