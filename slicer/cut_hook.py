"""Bind a campaign, space and ask to the cut checker, so a caller hands over only a molecule."""

from __future__ import annotations


def make_checker(campaign, space, ask, wall=None, check=None):
    """The callable forwards everything to `check` and returns its result unchanged."""
    def checker(molecule):
        run = check
        if run is None:
            from cut_check import check as run
        return run(molecule, campaign, space, ask, wall=wall)
    return checker
