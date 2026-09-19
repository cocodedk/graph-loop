"""The environment a model-call child gets, and the scratch it owns.

Every call this loop pays for — builder, reviewer, planner, codex — is started
through this one function, so the environment is decided once. It is a gate's
`gate_sandbox.environment` in the one part a model call can take: a builder is
handed its card's gate as text and runs it while it works, so `$TMPDIR` has to
name a directory somebody owns. It cannot take the rest of that box, which
masks the home the call's own credentials live in.

Split out of providers.py at the 200-line cap (CLAUDE.md): `providers._run`
stays the front door, and `provider_codex` still imports it from there.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import runner


def _run(argv: list[str], stdin: str, env: dict | None = None, timeout: int = 3600,
         cwd: str | None = None, drop: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    # `runner.run` takes the child's COMPLETE environment; this call's own
    # `env` is only ever a partial overlay, so it is merged onto a copy of
    # this process's environment before it travels any further.
    environment = dict(os.environ)
    environment.update(env or {})
    # Scratch this call owns: a gate that writes `"$TMPDIR/out"` writes to
    # `/out` when TMPDIR is unset, and into the driver's own scratch — where it
    # outlives every call — when it is set. `TemporaryDirectory` and not
    # `rmtree(ignore_errors=True)`: a build leaves read-only trees behind, and
    # a removal that swallows its own errors leaves the whole scratch on the
    # disk and says nothing. This one resets the mode and retries.
    scratch = tempfile.TemporaryDirectory(prefix="call-tmp-")
    environment["TMPDIR"] = scratch.name
    try:
        return runner.run(argv, stdin=stdin, env=environment, timeout=timeout,
                          cwd=cwd, drop=drop)
    finally:
        try:
            scratch.cleanup()
        except OSError as error:
            # By here the answer is bought — its text, its cost, its session —
            # or the timeout is the caller's to read. A scratch that will not
            # go is said out loud and named; it never leaves this `finally`,
            # because an exception raised here replaces whichever of those two
            # the call was about to hand back.
            print(f"[the call's scratch is left behind: {error}]", file=sys.stderr)
