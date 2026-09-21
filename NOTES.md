## 2026-09-21 (Codex) — supervise graph-loop repairing itself

**State:** The owner requires graph-loop to implement the four reviewed bugs,
skip finished cards and resume unfinished branch frontiers, and implement a
Jev model-and-effort router with validated choices and a fallback; the
supervisor prepares contracts and gates, observes runs, and pushes fixpoints.

**Tried:** Baseline: 1,558 driver and 211 slicer tests pass; Ruff and the
structural scrub pass. Independent reproductions found rename publication
retains the source, rename scope misses its destination, planning lifts a
human hold, and planning ignores the driver lock. Both model CLIs answered
medium-effort probes. Claude's installed CLI requires a supported permission
mode rather than the loop's old `default` argument.

**Lesson:** Passing the existing suite does not prove the missing behavior;
write a failing gate before asking the loop's independent builder to fix it.

**Next:** Commit gate-only preparation off main, run atomic cards through the
real driver with independent reviews, refresh the executing checkout at each
accepted fixpoint, and verify and push each fixpoint. Keep local campaign
logs and machine-specific launcher configuration outside tracked files.
