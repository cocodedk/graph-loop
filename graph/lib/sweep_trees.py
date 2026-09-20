"""Remove the worktrees of settled cards — mechanical, run by the supervisor's
ticker. A kept tree is evidence only while its card is open; once the card is
done or dropped, the decision about that work is recorded on the card and its
tree (a full clone, ~650 MB) is dead weight. 54 GB of them filled /tmp on
2026-09-03 and killed every process on the host, authentication included.

Only a tree a SETTLED card itself records (its `worktree` or `rebuild_from`)
is removed: an unknown tree, or one that merely shares a card's name — another
campaign's, say — is never touched.

    python3 sweep_trees.py [backlog-path] [--dry]     (default: the campaign's backlog)
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile

SETTLED = ("done", "dropped")


def sweep(tasks: list[dict], tmp: pathlib.Path, dry: bool = False) -> list[str]:
    """The tree paths removed (or, dry, that would be). A tree that will not go
    — held back, or one the removal failed on — is said on stderr and not
    counted; its parent stays with it. A parent goes only after its own tree
    went: an empty graph-* dir may be a build's parent made a moment ago,
    before its tree exists."""
    open_paths = {str(row.get(key)) for row in tasks for key in ("rebuild_from", "worktree")
                  if row.get(key) and row.get("status") not in SETTLED}
    settled_paths = {str(row.get(key)) for row in tasks for key in ("rebuild_from", "worktree")
                     if row.get(key) and row.get("status") in SETTLED}
    # A settled card whose paid edits were never written down keeps its tree:
    # the tree IS that work, and the card says so.
    held = {str(row.get(key)): str(row.get("edits_unsaved"))
            for row in tasks for key in ("rebuild_from", "worktree")
            if row.get(key) and row.get("edits_unsaved")}
    removed: list[str] = []
    for parent in sorted(tmp.glob("graph-*")):
        went = False
        for tree in sorted(parent.glob("task-*")):
            path = str(tree)
            if path in open_paths or path not in settled_paths:
                continue                      # open, unknown, or not this campaign's: stays
            if path in held:
                print(f"sweep_trees: {path} stays: {held[path]}", file=sys.stderr)
                continue
            if not dry:
                try:
                    shutil.rmtree(tree)
                except OSError as err:
                    print(f"sweep_trees: {path} stays: {err}", file=sys.stderr)
                    continue
            removed.append(path)
            went = True
        if went:
            try:
                parent.rmdir()
            except OSError:
                pass                          # not empty, or already gone
    return removed

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import where
    from backlog import Backlog
    dry = "--dry" in sys.argv
    named = [a for a in sys.argv[1:] if a != "--dry"]
    book = Backlog(named[0] if named else where.backlog())
    gone = sweep(book.tasks(), pathlib.Path(tempfile.gettempdir()), dry=dry)
    print(f"sweep_trees: {'would remove' if dry else 'removed'} {len(gone)} settled worktrees")
