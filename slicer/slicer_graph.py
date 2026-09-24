"""The prospective graph, and the questions the two laws ask of it.

Split from `slicer_law` at the 200-line cap, and kept out of
`slicer_owners` so neither of those imports the other: both read this, and
a cycle between them would depend on which was imported first.
"""

from __future__ import annotations


def _graph(name: str, made: dict, rows: list[dict],
           target: dict | None) -> tuple[dict, list[str]]:
    """The whole prospective graph — the backlog as it stands plus what this
    answer would publish — and the ids the answer claims, in stage order.

    One home, because two laws ask the same question of it: no wait runs in a
    circle, and no two cards that can run at once grant the same file.
    """
    graph = {str(row.get("id")): list(row.get("needs") or []) for row in rows}
    atoms = sorted(made.get("atoms") or [], key=lambda atom: atom["stage"])
    ids = [f"{name}.{atom['name']}" for atom in atoms]
    # the writer owns lineage: a replaced leaf hands its own waits down (tree.publish)
    outside = list((target or made).get("needs") or [])
    published: list[str] = []
    ahead: list[str] = []
    stage = None
    for atom, atom_id in zip(atoms, ids):
        if atom["stage"] != stage:
            stage, ahead = atom["stage"], list(published)
        graph[atom_id] = (ahead or outside) + [wait for wait in (atom.get("needs") or [])
                                               if wait not in outside]
        published.append(atom_id)
    graph[name] = outside + ids
    if target:
        graph[str(target["id"])] = list(target.get("needs") or []) + [name]
    return graph, ids


def _assert_no_cycle(graph: dict) -> None:
    import graphlib
    try:
        graphlib.TopologicalSorter(graph).prepare()
    except graphlib.CycleError as circle:
        raise ValueError("these waits run in a circle: "
                         + " → ".join(circle.args[1])) from circle


def _ordered(graph: dict, one: str, other: str) -> bool:
    """Whether either card waits, however far back, on the other."""
    return _reaches(graph, one, other) or _reaches(graph, other, one)


def _reaches(graph: dict, start: str, goal: str) -> bool:
    seen, edge = set(), [start]
    while edge:
        here = edge.pop()
        if here == goal:
            return True
        if here in seen:
            continue
        seen.add(here)
        edge.extend(str(wait) for wait in graph.get(here) or [])
    return False
