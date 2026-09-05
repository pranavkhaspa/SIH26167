#!/usr/bin/env bash
# SatQuery AI — deterministic verification gate for the build farm.
# Banned: `|| true`. Exit code is the ONLY signal the farm trusts.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> verify: backend tests (pytest)"
if [ ! -d venv ]; then
  echo "==> no venv, creating one"
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r backend/requirements.txt

# Run from backend/ so `from app...` imports resolve
cd backend
python -m pytest tests/ -q
echo "==> verify: PASS — all tests green"