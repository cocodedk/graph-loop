#!/bin/sh
set -eu
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "Hooks installed — pre-commit, commit-msg and pre-push (owner-locked) are active."
