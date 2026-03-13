#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[regression] python compile check"
PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests >/dev/null

echo "[regression] backend pytest"
PYTHONPATH=. python3 -m pytest -q backend/tests

echo "[regression] frontend dependencies"
if [[ ! -d frontend/node_modules ]]; then
  npm --prefix frontend install
fi

echo "[regression] frontend unit/component tests"
npm --prefix frontend run test:run

if [[ "${SKIP_PLAYWRIGHT:-0}" == "1" ]]; then
  echo "[regression] skipping playwright e2e (SKIP_PLAYWRIGHT=1)"
else
  echo "[regression] frontend e2e smoke"
  npm --prefix frontend run test:e2e
fi

echo "[regression] completed"
