#!/usr/bin/env bash
# SatQuery AI — one build-farm cycle (agent loop contract).
#
# Flow:
#   1. Main agent has already written the current task spec into entry_point.md
#      and updated plan.md status to IN_PROGRESS.
#   2. This script:  run verify gate -> if green, commit the work -> push staging.
# If the gate fails, it exits non-zero; the farm sends the failure back to the
# coder (see plan.md "Execution Loop"). No push happens on red.
set -euo pipefail

cd "$(dirname "$0")/.."

BRANCH="${1:-staging}"
MSG="${2:-ci: build-farm cycle — entry_point.md task}"

echo "==> cycle: verify gate"
./farm/verify.sh

echo "==> cycle: stage & commit"
git add -A
git commit -m "$MSG" || { echo "nothing to commit or commit failed"; exit 0; }

echo "==> cycle: push to $BRANCH"
git push origin "$BRANCH"
echo "==> cycle: DONE — pushed $BRANCH (human QA next)"