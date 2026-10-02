"""Own one command's descendants, including children that detach twice.

The kernel adopts orphaned descendants into this process. Closing repeatedly
kills and reaps only its direct children; no process-name or machine-wide scan
is involved. A child cannot have its pid reused until this parent reaps it.
"""

from __future__ import annotations

import ctypes
import os
import pathlib
import signal
import subprocess
import sys
import time


def close_children() -> None:
    children = pathlib.Path(f"/proc/self/task/{os.getpid()}/children")
    while True:
        for pid in children.read_text().split():
            try:
                os.kill(int(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            while os.waitpid(-1, os.WNOHANG)[0]:
                pass
        except ChildProcessError:
            return
        time.sleep(0.01)


def main(argv: list[str]) -> int:
    stopped = 0

    def stop(number, _frame):
        nonlocal stopped
        stopped = number

    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, stop)
    kernel = ctypes.CDLL(None, use_errno=True)
    # Adopt descendants before launching anything; die-with-parent is reset by
    # exec on some platforms, so bind again and check the expected parent.
    if kernel.prctl(36, 1) != 0 or kernel.prctl(1, signal.SIGTERM) != 0:
        raise OSError(ctypes.get_errno(), "cannot own command descendants")
    if os.getppid() != int(argv[0]) or stopped:
        return 125
    try:
        command = subprocess.Popen(argv[1:])  # inherits the caller's pipes and environment
        while command.poll() is None and not stopped:
            time.sleep(0.02)
        code = command.returncode
        return 128 + stopped if stopped else (code if code >= 0 else 128 - code)
    finally:
        close_children()


if __name__ == "__main__":
    try:
        result = main(sys.argv[1:])
    except OSError as fault:
        print(f"command ownership failed: {fault}", file=sys.stderr)
        result = 125
    raise SystemExit(result)
