"""Reading the campaign's log back: where the clock went, where the money went.

The loop times every step and writes every prompt, answer, diff and gate output
down. This turns that record into the two answers a person actually needs: which
step is the bottleneck, and what the campaign is paying for.

Steps are grouped into work (a builder writing, a gate running) and judging
(proving a gate red, the two reviews). A campaign that spends most of its clock
judging is not necessarily wrong — refusing early is cheap — but it is the number
to look at first.
"""

from __future__ import annotations

from report_cuts import cut_line, cuts


def _local_hhmm(at: str) -> str:
    """The log stores UTC; a person reads the clock on the wall."""
    import datetime
    try:
        stamp = datetime.datetime.strptime(at + "+0000", "%Y-%m-%dT%H:%M:%SZ%z")
        return stamp.astimezone().strftime("%H:%M")
    except ValueError:
        return at[11:16]


def _since_accept(rows: list[dict]) -> list[dict]:
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].get("kind") == "accepted":
            return rows[index + 1:]
    return rows


WORK_STEPS = ("build", "gate")
JUDGE_STEPS = ("red_first", "contract", "diff_review")


def turns(rows: list[dict]) -> list[dict]:
    """Each turn's frontier width against the lanes it could run, in order.

    Read from the one record the turn wrote (`turn_plan.width_against_lanes`),
    never recomputed here: a second reading of the graph days later is a
    different graph, because the backlog is re-sliced between runs.
    """
    return [{"turn": str(row.get("turn") or "?"), "at": str(row.get("at") or ""),
             "width": int(row.get("width") or 0), "cap": int(row.get("cap") or 0),
             "lanes": int(row.get("lanes") or 0)}
            for row in rows if row.get("kind") == "turn_lanes"]


def report(space) -> dict:
    rows = space.events()
    steps = [row for row in rows if row.get("kind") == "step"]
    attempts = [row for row in rows if row.get("kind") == "attempt"]
    # A rejection queued for its next round is a rejection all the same: the
    # report counts every reviewer refusal, not only the ones that ended a task.
    refusals = [row for row in rows
                if row.get("kind") in ("refused", "rejected", "rebuild_queued", "failed")]

    by_step: dict[str, dict] = {}
    for row in steps:
        name = row.get("step") or "unknown"
        entry = by_step.setdefault(name, {"seconds": 0.0, "calls": 0, "share": 0.0})
        entry["seconds"] += float(row.get("seconds") or 0)
        entry["calls"] += 1

    total = sum(entry["seconds"] for entry in by_step.values())
    for entry in by_step.values():
        entry["share"] = round(100.0 * entry["seconds"] / total, 1) if total else 0.0

    by_task: dict[str, float] = {}
    for row in steps:
        by_task[row.get("task", "?")] = by_task.get(row.get("task", "?"), 0.0) + \
            float(row.get("seconds") or 0)

    per_turn = turns(rows)
    counted = [row for row in attempts if row.get("counted")]
    reviews = [row for row in attempts if row.get("purpose") == "review"]
    decisions = [row for row in attempts if row.get("purpose") == "decide"]
    # A router decision is a "routed" event, not an "attempt" — it never
    # consumes a build attempt — but its measured fee is spend all the same,
    # a paid decision that fell back included, an offline route (no figure)
    # never turned into an invented zero-cost charge.
    routed = [row for row in rows if row.get("kind") == "routed"]
    return {
        "turns": per_turn,
        # The turns where the graph branched out further than the loop could
        # follow: the frontier the owner's rule is about, and the one number
        # that says whether the cap is costing anything.
        "turns_wider": [row["turn"] for row in per_turn if row["width"] > row["cap"]],
        "tasks": len(by_task),
        "seconds": round(total, 1),
        "by_step": by_step,
        "by_task": {name: round(seconds, 1) for name, seconds in by_task.items()},
        "slowest_step": max(by_step, key=lambda name: by_step[name]["seconds"])
        if by_step else None,
        "slowest_task": max(by_task, key=lambda name: by_task[name]) if by_task else None,
        "seconds_on_work": round(sum(entry["seconds"] for name, entry in by_step.items()
                                     if name in WORK_STEPS), 1),
        "seconds_on_judging": round(sum(entry["seconds"] for name, entry in by_step.items()
                                        if name in JUDGE_STEPS), 1),
        "spend_known": round(sum(row.get("cost") or 0 for row in attempts) +
                             sum(row.get("cost") or 0 for row in routed), 4),
        # Codex has no account of its own and Claude shares builder accounts,
        # so a review call is told apart only by `purpose="review"`
        # (workspace.py `attempt`). A review with no cost figure is counted,
        # never folded into the known total as a silent zero.
        "review_spend_known": round(sum(row["cost"] for row in reviews
                                        if row.get("cost") is not None), 4),
        "review_calls_unknown_cost": sum(1 for row in reviews if row.get("cost") is None),
        # A decision is told apart the same way, and codex reports no figure at
        # all: unknown is counted, never folded in as a silent zero.
        "decide_spend_known": round(sum(row["cost"] for row in decisions
                                        if row.get("cost") is not None), 4),
        "decide_calls_unknown_cost": sum(1 for row in decisions if row.get("cost") is None),
        "attempts": len(counted),
        "uncounted_calls": len(attempts) - len(counted),
        "refusals": len(refusals),
        # The whole history is in the log; a report that reprints it buries the
        # two that still matter.
        "refusal_reasons": [
            f"{_local_hhmm(row['at'])}  "
            + " ".join(str(row.get("why") or "").split())
            for row in refusals[-2:]
        ],
        "refusals_since_accept": len([row for row in _since_accept(rows)
                                      if row.get("kind") in
                                      ("refused", "rejected", "rebuild_queued", "failed")]),
        "accepts": sum(1 for row in rows if row.get("kind") == "accepted"),
        "artifacts": sum(1 for row in rows if row.get("kind") == "artifact"),
        "cuts": cuts(space),
    }


def as_text(out: dict) -> str:
    """The report a person reads: the bottleneck first, then the detail."""
    opening = (f"tasks touched: {out['tasks']}   clock: {out['seconds']}s   "
               f"known spend: ${out['spend_known']:.2f}   answered calls: "
               f"{out['attempts']} "
               f"(+{out['uncounted_calls']} that did not count as attempts)")
    lines = [opening]
    if out["review_spend_known"] or out["review_calls_unknown_cost"]:
        lines.append(f"reviews: ${out['review_spend_known']:.2f} known, "
                     f"{out['review_calls_unknown_cost']} calls with no figure")
    if out["decide_spend_known"] or out["decide_calls_unknown_cost"]:
        unknown = out["decide_calls_unknown_cost"]
        lines.append(f"decisions: ${out['decide_spend_known']:.2f} known, "
                     f"{unknown} call{'' if unknown == 1 else 's'} with no figure")
    if out["slowest_step"]:
        entry = out["by_step"][out["slowest_step"]]
        lines.append(f"bottleneck: {out['slowest_step']} — {entry['seconds']:.0f}s over "
                     f"{entry['calls']} calls, {entry['share']}% of the clock")
    lines.append(f"work {out['seconds_on_work']}s   judging {out['seconds_on_judging']}s")
    for name, entry in sorted(out["by_step"].items(),
                              key=lambda pair: -pair[1]["seconds"]):
        lines.append(f"  {name:<12} {entry['seconds']:>7.1f}s  {entry['share']:>5.1f}%  "
                     f"{entry['calls']} calls")
    if out["by_task"]:
        slowest = sorted(out["by_task"].items(), key=lambda pair: -pair[1])[:5]
        lines.append("slowest tasks: " +
                     ", ".join(f"{name} {seconds:.0f}s" for name, seconds in slowest))
    if out["refusals"]:
        import textwrap
        # before any acceptance there is no "last accepted card" to count from,
        # and the running refusals are current, never history
        lines.append((f"refusals since the last accepted card: {out['refusals_since_accept']} "
                      f"(the whole campaign has seen {out['refusals']} — history, not news); "
                      if out["accepts"] else
                      f"refusals since the campaign start: {out['refusals']} "
                      "(nothing accepted yet); ")
                     + "the last two, with the time they happened:")
        for why in out["refusal_reasons"]:
            first = why.split(". 2.")[0].split(" 2. ")[0]
            wrapped = textwrap.wrap(first, 88)[:2] or [""]
            lines.append(f"  - {wrapped[0]}")
            lines.extend(f"    {line}" for line in wrapped[1:])
        lines.append("  (every refusal in full: calls/<task>/*-contract-answer.txt)")
    if out["turns"]:
        wider = out["turns_wider"]
        lines.append(f"frontier against lanes: {len(out['turns'])} turn(s) recorded, "
                     f"{len(wider)} where the graph was wider than the loop")
        for turn in out["turns"][-5:]:
            lines.append(f"  {_local_hhmm(turn['at'])}  {turn['turn']}  "
                         f"width {turn['width']}  cap {turn['cap']}  "
                         f"lanes {turn['lanes']}"
                         + ("  — wider than the loop" if turn["width"] > turn["cap"] else ""))
        if wider:
            lines.append("  wider than the loop: " + ", ".join(wider[:5])
                         + (f" (+{len(wider) - 5} more)" if len(wider) > 5 else ""))
    lines.append(cut_line(out))
    lines.append(f"everything said and seen is written down: {out['artifacts']} files "
                 "under calls/")
    return "\n".join(lines)
