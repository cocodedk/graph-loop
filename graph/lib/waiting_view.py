"""The specs of a project that need a person: read from its docs/lean and its merged history, nothing written."""

from __future__ import annotations

import os

import lean_spec
import project_specs
from project_specs import MARK_STYLE, PR_OPEN, QUESTION, STOPPED


def specs_of(folder: str) -> list[tuple[str, str, str]]:
    """The (spec, mark, colour) of each spec in `folder` that needs a person; none when it cannot be read."""
    if not os.path.isdir(os.path.join(folder, "docs", "lean")):
        return []
    try:
        built = project_specs.built_names(folder)
        return [(lean_spec.slug(path.name), mark, MARK_STYLE[mark]) for path in project_specs.spec_files(folder)
                if (mark := project_specs.mark(path, set(), built)) in (QUESTION, STOPPED, PR_OPEN)]
    except OSError:
        return []
