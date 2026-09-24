# Contributing to graph-loop

## Local setup

1. Python 3.12 or newer.
2. `python3 -m pip install pyyaml ruff`
3. Install the hooks — they are not active in a fresh clone until you do:

```
./scripts/install-hooks.sh
```

## Local git configuration

Run these once after cloning:

```bash
git config pull.rebase true
git config core.autocrlf input       # use `true` on Windows
git config push.autoSetupRemote true
```

## Build and test

```
(cd slicer/tests && python3 -m unittest discover -q)
(cd graph/tests && python3 -m unittest discover -q)
ruff check .
bash scripts/scrub-check.sh
```

The check ships structural patterns only. While material is still being lifted out of the
work this loop came from, pass that migration's private denylist by path as well:

```
bash scripts/scrub-check.sh /path/to/denylist
```

## Nothing local travels

This repository is public and the loop it carries was built inside a private
engagement. `scripts/scrub-check.sh` fails the build if an account name, a home
directory, a private repository name or a foreign commit hash reaches a tracked
file. It runs in CI. If it fails, fix the file — never the check.

## Coding style

Follow the [KISS repair rule](CLAUDE.md#kiss-repair-rule).

- Every file under 200 lines. A file that outgrows it splits at a natural seam,
  and the old name stays as the front door.
- One job per module, and the job is stated in the first line of its docstring.
- Boring over clever. Deletion over addition. If the explanation would be longer
  than the code, delete the explanation.
- Standard library first. The only runtime dependency is PyYAML, and adding a
  second one needs a reason in the pull request.

## Branch naming

Kebab-case, prefix matching the conventional-commit type used in the PR:
`feature/`, `fix/`, `chore/`, `docs/`, `refactor/`, `ci/`. Never commit directly
to `main` — open a pull request.

## Commit messages

Conventional Commits, enforced by the `commit-msg` hook:
`feat|fix|chore|docs|style|refactor|test|ci|build|perf|revert: description`

## Pull request checklist

- [ ] Tests pass.
- [ ] `ruff check .` is clean.
- [ ] `scripts/scrub-check.sh` passes.
- [ ] A new check has been made to fail in front of you before you trust it.
- [ ] Docs updated if behaviour changed.
