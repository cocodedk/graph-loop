"""Fresh JUnit failures, appended to the console evidence without hiding it."""

from __future__ import annotations

import pathlib
import re
import xml.etree.ElementTree as ET

from issue_scrub import scrub

HEADING = "\n\nJUnit failures:\n"
LIMIT = 2000
CASES = 20
FAILING = re.compile(r"FAIL|ERROR:|AssertionError|[✗×✖]")   # what a test runner prints for a failed case
# A runner's summary: "2 failed, 1 error" (pytest, jest, gradle, cargo) or unittest's "failures=2, errors=1".
SUMMARY = re.compile(r"(\d+) (?:failed|errors?)\b|\b(?:failures|errors)=(\d+)")


def excerpt(text: str, *, tail: bool = True) -> str:
    """Keep the existing console window AND the already bounded XML digest.

    Reasons and artifacts are plain text throughout the loop; their heading
    marks the digest so later readers do not cut it or the console away.
    """
    console, heading, digest = text.partition(HEADING)
    failing = [line.strip()[:200] for line in console[:-LIMIT].splitlines() if FAILING.search(line)] if tail else []
    earlier = "[failing lines before the tail]\n" + "\n".join(failing[-CASES:]) + "\n[the tail]\n" if failing else ""
    return earlier + (console[-LIMIT:] if tail else console[:LIMIT]) + heading + digest


def failing(text: str) -> int:
    """How many lines of a gate's output a test runner marks as a failed case."""
    return sum(1 for line in text.splitlines() if FAILING.search(line))


def failures(text: str) -> tuple[int, int]:
    """(the failed cases the runner's last summary line counts, or 0 without one; the failing lines), to
    compare in order: fewer failed tests is progress, and so is the same count with fewer failing lines."""
    summaries = [line for line in text.splitlines() if SUMMARY.search(line)]
    counted = sum(int(a or b) for a, b in SUMMARY.findall(summaries[-1])) if summaries else 0
    return counted, failing(text)


def junit_failures(cwd: str, started: int) -> str:
    """Newest reports first, only mtimes at or after this gate's start (ns)."""
    root = pathlib.Path(cwd).resolve()
    reports = []
    for path in root.glob("**/build/test-results/**/TEST-*.xml"):
        try:
            if not path.resolve().is_relative_to(root) or not path.is_file():
                continue
            mtime = path.stat().st_mtime_ns
            if mtime >= started:
                reports.append((mtime, path))
        except OSError:
            continue  # a report removed while looking is not evidence
    lines, total = [], 0
    for _, path in sorted(reports, key=lambda item: (-item[0], item[1])):
        try:
            suite = ET.parse(path)
        except (OSError, ET.ParseError):
            continue  # partial/unreadable XML must never change the gate's verdict
        for case in suite.iterfind(".//{*}testcase"):
            failure = case.find("{*}failure")
            if failure is None:
                failure = case.find("{*}error")
            if failure is None:
                continue
            total += 1
            if len(lines) < CASES:
                message = (failure.get("message") or failure.text or "").splitlines()
                line = (f"- {case.get('classname', '')}.{case.get('name', '')}: "
                        f"{failure.get('type', '')}: {message[0] if message else ''}")
                lines.append(scrub(line, set()))
    if not total:
        return ""
    while True:
        more = f"\n… and {total - len(lines)} more" if total > len(lines) else ""
        digest = HEADING + "\n".join(lines) + more
        if len(digest) <= LIMIT:
            return digest
        lines.pop()
