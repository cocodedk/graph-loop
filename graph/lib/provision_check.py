"""Before planning or a run: nothing the loop provisions may enter a checkout's diff.

`provision` links or copies gitignored material into every checkout the loop
makes. When git would carry any of it, every build's diff carries it too and no
card can be kept: one campaign spent 352 attempts that way before anyone looked.
One probe checkout of the commit the next card would start from, made before any
card starts and before any model is paid, finds it for free.

The supervisor asks before its plan phase and stands down for a person unless the
answer is exit 0: a refusal and a probe that failed are both reasons not to pay
for a plan phase. `run` asks again before it claims the campaign, for a run
started by hand.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

from keep import Keeper
from worktree import Worktree
from worktree_provision import carried, named


def refusal(repo: str, branch: str) -> str:
    """Why the run must not start, or "" when provisioning is safe or absent."""
    if not (named("GRAPH_PROVISION_LINK") or named("GRAPH_PROVISION_COPY")):
        return ""
    commit = Keeper(repo, branch).tip()   # where the next card starts, read as the keeper reads it
    parent = tempfile.mkdtemp(prefix="graph-provision-check-")
    try:
        probe = Worktree(repo, "provision-check", commit=commit).create(parent=parent)
        lines = carried(probe.path)
    finally:
        _remove(parent)
    if not lines:
        return ""
    return ("the run did not start: git would carry what GRAPH_PROVISION_LINK and "
            "GRAPH_PROVISION_COPY put into each checkout into every build's diff:\n"
            + "\n".join(f"  {line}" for line in lines)
            + "\nIgnore it in the repository's .gitignore. A linked folder is a symlink, which a "
              "pattern ending in '/' does not match, so name it without the '/'.")


def _remove(parent: str) -> None:
    """The probe goes, copied read-only folders included, and never through a link:
    a linked folder is the repository's own, and its permissions are not ours."""
    for root, folders, _files in os.walk(parent):
        for name in folders:
            path = os.path.join(root, name)
            if not os.path.islink(path):
                os.chmod(path, 0o700)
    shutil.rmtree(parent)


if __name__ == "__main__":      # supervisor.sh asks before its plan phase: only exit 0 is safe
    if named("GRAPH_PROVISION_LINK") or named("GRAPH_PROVISION_COPY"):   # else nothing to ask
        from campaign_of import branch_of
        from where import repo
        from workspace import Workspace
        space = Workspace(sys.argv[1])
        why = refusal(str(repo(space, persist=False)), branch_of(space))
        if why:
            print(why)
            raise SystemExit(1)
