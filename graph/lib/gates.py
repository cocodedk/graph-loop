"""Running a gate, and proving it red before anyone builds against it.

Two rules, both bought with failures: a gate's verdict is its exit code, never
text something happened to match (`gate.sh | grep GATE && git commit` once
committed a red gate), and a gate that has never failed is not a gate — so a task
starts only after its gate refuses for the reason the task exists to fix,
unless there is nothing to build: a no-files, non-live card's gate is never
proved red, only run once, after the contract review, deciding done or
failed on its own.
"""

from __future__ import annotations

import dataclasses
import shutil
import subprocess
import tempfile
import time

import gate_sandbox
import runner
from gate_reports import excerpt, junit_failures
from provider_words import environment_hint

DEFAULT_TIMEOUT = 3600


@dataclasses.dataclass
class GateResult:
    code: int
    output: str
    kind: str = "ran"        # ran | timeout | crash
    confined: bool = False   # whether the box actually held, not whether it was asked for

    @property
    def passed(self) -> bool:
        return self.kind == "ran" and self.code == 0

    @property
    def why(self) -> str:
        return excerpt(self.output)


GREEN_ALREADY = "the gate already passes, so it proves nothing"   # the one wording red_first matches exactly

def run_gate(command: str, cwd: str, timeout: int = DEFAULT_TIMEOUT,
             confine: bool = True, paths=None) -> GateResult:
    """One gate, in its own shell, inside `gate_sandbox`'s box. Both streams are
    kept: a failure the builder cannot read does not exist.

    `confine=False` is for a LIVE gate only: it performs the work it measures,
    it needs Docker and the database, and its text is the commander's.
    """
    # Never made for an unconfined (LIVE) gate: nothing below reads it then.
    home = tempfile.mkdtemp(prefix="gate-home-") if confine else ""
    boxed = confine and gate_sandbox.works()
    argv = (gate_sandbox.argv(command, cwd, home, **({"paths": paths} if paths else {}))
            if boxed else ["bash", "-c", command])
    # The scrub does not need the box: it is the environment this call is given,
    # so a host without bubblewrap still keeps its credentials out of the gate.
    env = gate_sandbox.environment(home) if confine else None
    started = time.time_ns()
    try:
        done = runner.run(argv, env=env, cwd=cwd, timeout=timeout)
        result = GateResult(done.returncode, (done.stdout or "") + (done.stderr or ""),
                            confined=boxed)
    except subprocess.TimeoutExpired as expired:
        # `runner.run` always runs in text mode, so this is always a str;
        # the isinstance check only narrows the type `TimeoutExpired` declares.
        text = expired.stdout if isinstance(expired.stdout, str) else ""
        result = GateResult(124, text + f"\n[the gate did not return inside {timeout}s]",
                          kind="timeout", confined=boxed)
    except OSError as error:
        result = GateResult(127, str(error), kind="crash", confined=boxed)
    finally:
        # the empty home is this call's alone: left behind, one per gate run,
        # 196 of them filled /tmp in an hour and the full disk of 2026-09-03
        # killed every process on the host
        if home:
            shutil.rmtree(home, ignore_errors=True)
    if not result.passed:
        result.output += junit_failures(cwd, started)
    return result


def prove_red(command: str, cwd: str, expect: str = "",
              timeout: int = DEFAULT_TIMEOUT, confine: bool = True, paths=None) -> tuple[bool, str]:
    """Refuse the task unless its gate fails now, for the stated reason.

    Returns (proved, why). `expect` is a phrase the refusal must contain — the
    guard against a gate that is red for somebody else's reason, which is how two
    packages burned four attempts on rows they were not allowed to touch.
    """
    result = run_gate(command, cwd, timeout, confine=confine,
                      **({"paths": paths} if paths else {}))
    if result.passed:
        return False, GREEN_ALREADY
    if environment_hint(result.output, command):
        return False, result.output  # classify before a long footer can hide the toolchain error
    if result.kind != "ran":
        return False, f"the gate could not run ({result.kind}): {result.why}"
    if expect and expect not in result.output:
        return False, ("the gate is red for another reason; expected "
                       f"{expect!r} in:\n{result.why}")
    return True, result.why
