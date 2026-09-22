"""Read-only counts for cards that name a node."""


from workspace_claims import _now


def say(rows: list[dict]) -> None:
    nodes: dict[str, list] = {}
    for row in rows:
        node = str(row.get("node") or "").strip()
        if node:
            nodes.setdefault(node, []).append(row)
    for node, cards in sorted(nodes.items()):
        done = sum(card.get("status") == "done" for card in cards)
        opened = len(cards) - done
        print(f"{_now()} " + (f"  node {node}: {done} done / {opened} open" + (" — built" if not opened else "")).replace("\n", f"\n{_now()} "), flush=True)
