"""What a CODE builder may run: the fixed base, and the floor over its gate.

Split out of `tools.py` at the 200-line cap; `tools` stays the front door and
re-exports all three names.

Three files, three jobs, and the fresh review of PR #37 is why they are apart:
`gate_programs` READS the programs out of a gate's text and is careful about it,
this GRANTS a subset of them, and the two were one thing while the granting was
wrong. A reader that tells the truth about what a gate runs is useful to every
caller; what may then be handed to a builder is a separate question with a
separate answer.
"""

from __future__ import annotations

from gate_programs import programs
from gate_script import gate_script_path

# Reading and version control: what every card needs whatever it is written in.
# Nothing language-specific belongs here — see `code_shell` below.
BASE_SHELL = ("Bash(git *),Bash(sed -n *),Bash(cat *),Bash(head *),Bash(tail *),Bash(ls *),"
              "Bash(grep *),Bash(wc *)")


# The floor under a grant derived from a gate the PLANNER MODEL wrote. A grant
# is `Bash(<name> *)`, which is not one command but everything that name can be
# asked to do, and for these that is the whole machine: a shell or a runner
# executes anything handed to it, `sudo` and `su` reach another identity, a
# container is root on this host, and a downloader reaches the network. A
# model-written gate naming `curl`, `bash` and `sudo` granted all three (the
# fresh review of PR #37, finding 4), which is the `Bash(bash *)` escape hatch
# the old fixed list was called out for. The list is by CATEGORY, not by the
# three names that were caught: `find -exec` and `awk`'s `system()` are a shell
# by another name, and the review's second pass caught them left out.
#
# It costs the gate nothing: `Bash(bash <gate script>)` below authorises the
# gate's own fixed script, which is the narrow form, so a gate that opens with
# `bash` still runs. What it refuses is the WILDCARD beside it.
#
# It is a floor, not a sandbox, and the docstring above should not be read as
# one: a card's own language runtime is granted (`python3 -c` is arbitrary code
# by design, and refusing it would refuse every Python campaign), and the
# worktree and the file fence are what actually bound a builder. This stops a
# gate's text from being a way to ask for the categories no card's language is.
NEVER_WILDCARD = frozenset({
    # a shell, or anything whose job is to run the command you hand it
    "bash", "sh", "zsh", "dash", "ksh", "csh", "fish", "env", "xargs", "nohup",
    # the same thing wearing another hat: `find -exec`, `awk 'BEGIN{system(…)}'`
    "find", "awk", "gawk", "mawk",
    # another identity, or a container that is root on this host
    "sudo", "su", "doas", "docker", "docker-compose", "podman", "kubectl",
    # another machine
    "ssh", "scp", "sftp", "rsync", "telnet",
    # the network
    "curl", "wget", "nc", "ncat", "netcat", "socat",
})


def code_shell(task: dict) -> str:
    """What a CODE builder may run: the base, plus the programs this card's own
    gate runs.

    It was a fixed list with `python3` and one linter in it, so the loop could plan
    a project in any language and build only a Python one — a Java card's
    builder could not run `javac` and every one of them parked (2026-09-18).

    Derived, not listed, because a list is a wall that moves: the card's gate is
    written by the slicer, refused or accepted by an independent reviewer before
    any build, and then RUN as the verdict. Its programs are already declared,
    already reviewed, and already going to execute.

    It is still a widening, and saying otherwise was the mistake: the gate runs
    ONE fixed command line and a grant is `<name> *`, every invocation of that
    name. For most programs that is the card's own language and the widening is
    worth it; for a shell, a runner, `sudo` or a downloader it is the machine,
    so `NEVER_WILDCARD` is the floor under it.

    The denies are untouched by any of this: `PUSH_DENY` and, for a live card,
    `STACK_DENIES` are deny rules, and no grant derived from a gate outranks
    them.
    """
    gate = str(task.get("gate") or "")
    named = ",".join(f"Bash({one} *)" for one in programs(gate)
                     if one not in NEVER_WILDCARD)
    # The gate itself, as one fixed path (`gate_script`). A per-program grant
    # authorises a command whose first word is that program, and a gate is a
    # script — `set -e -o pipefail`, an assignment from `mktemp`, then the work
    # — which no per-program rule describes: a Java builder handed
    # javac/java/mktemp had its own gate denied and improvised (2026-09-18).
    # The programs stay beside it, because a builder that reads a failure wants
    # to run one of them on its own before running the whole gate.
    own = f"Bash(bash {gate_script_path(task)})" if gate.strip() else ""
    return ",".join(part for part in (BASE_SHELL, own, named) if part)
