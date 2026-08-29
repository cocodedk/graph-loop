# Status, and where to pick this up

Last updated 29 August 2026.

This repository is being filled in two stages on purpose. If you are returning to it — from
another machine, or after a gap — read this first.

## The decision that shapes everything

- **Now:** the design, the diary and the skill. They carry the transferable value, and they
  do not change when someone fixes a bug in the code.
- **Later, in one move:** the runtime — roughly 4,150 lines of Python, two shell scripts and
  thirteen test files — once the work it currently serves has finished.

The reason is drift. The existing copy is patched on almost every run; one campaign alone
found six defects in the loop itself. Copying the code now would create a fork whose
*exercised* side is the one still in use and whose *clean* side is the one nobody runs, and
every fix would have to be carried across by hand into code that had been renamed in the
meantime. So the code moves once, from a source that has stopped moving.

## What is done

- The skill, the design and the diary, generalised and scrubbed.
- Plugin and marketplace manifests, so the skill installs.
- GitHub infrastructure: owner-locked pre-push hook, conventional-commit gate, CI, release
  from the plugin manifest, dependabot, templates, security policy, contributing guide.
- `scripts/scrub-check.sh`, and the discipline behind it — see below.
- Published, with CI green and branch protection active on `main`: `verify` must pass,
  a pull request is required, no force-push and no deletion. The repository owner can
  bypass, which is what makes a direct push to `main` possible — use it sparingly, because
  the protection is only as real as the habit.

## What is not done

- No GitHub Pages site, no `llms.txt`.
- The runtime, the tests, and the commands — deferred by the decision above.

## The open design question — read this before writing any command

A campaign runs for days. The thing that actually runs it is the supervisor, not the
driver: the driver is a process, processes die, and the supervisor restarts it and gives up
after repeated immediate failures.

That has a consequence the original design never wrote down. **A front end cannot hold a
session open waiting for a campaign to end.** Any `run` command must start the supervisor
and return; the watching commands must read state from the campaign's log, not from a
process the session owns. The existing dashboard decides whether the supervisor is alive by
looking for its filename in the process list, which is a dependency on that filename that
nothing declares.

Until that is settled, the honest description of this plugin is: a skill, plus the commands
that read a campaign rather than start one. Whether the loop belongs in a plugin at all, or
in a command-line tool with a thin plugin carrying the skill, is genuinely open.

## Known problems in the code that is coming

Found by review, not yet fixed. They are why the move is not a copy:

- The worktree builder copies four directories belonging to one project into every worktree
  it creates. That is behaviour, not prose — carried across unchanged it would silently
  special-case work nobody else has.
- One project's house rules sit inside the builder's prompt: a file-size limit, a ban on
  touching containers, an assumption that nobody is around at the weekend.
- The tool allowlist names a linter that exists on one set of machines.
- The doctor looks for the supervisor at a path spelled the way one repository spells it,
  in a branch that is a no-op and should be deleted rather than moved.
- The repository root is computed at import time, so making it fail loudly when unset needs
  care or `--help` and every test import will crash.
- The backlog schema is documented only in the header of a file that is not being
  extracted. It needs shipping as an example, or nobody can write a backlog.
- The builder's tool allowlist already grants arbitrary execution, so it is not a security
  boundary. The worktree, the scope check and the gate are. The security policy should say
  so rather than implying otherwise.

## The rules this repository already bought

- **A document is not authority about the code it describes.** The design shipped claiming
  the logic was generic; four places in the source said otherwise. A claim of genericness
  is a measurement, and the measurement is a grep of the source, spelled the way the source
  spells it.
- **Take the file list from the repository, not from a document.** A hand-written inventory
  drifts; `git ls-files` does not.
- **A new check is not trusted until the case it exists to catch has failed in front of
  you.** The guard here contained every literal it forbade and excluded itself to pass. Then
  it failed on its own pattern file. Then it caught a leak that had been committed and
  deleted, which a working-tree scan passes and a history scan does not. Every one of those
  was found by trying to break it, none by reading it.

## The notes that are not here

Some of this migration's detail names the work the loop came from — which repository, which
branch, which commit, and the literals the guard checks for. That is kept in a private
companion repository and is deliberately absent here. Everything in it that can be said
without naming anything is already above.

## Pick up here

1. Answer the operational question above — detached `run`, or a narrower plugin.
2. Write the backlog schema up as `examples/`, which can be done before the code arrives.
3. When the source has stopped moving: the runtime, in one move. Sanitise in a staging
   directory that is not a git repository, and let the scrub check pass **before** anything
   enters the index — a clean final checkout does not clean a history.
