#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! "$PYTHON_BIN" -c "import pytest" >/dev/null 2>&1; then
  for candidate in "$ROOT_DIR/.venv/bin/python" "/tmp/nas-diff-venv/bin/python"; do
    if [[ -x "$candidate" ]] && "$candidate" -c "import pytest" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if ! "$PYTHON_BIN" -c "import pytest" >/dev/null 2>&1; then
  echo "[regression] pytest is unavailable for python interpreter '$PYTHON_BIN'" >&2
  echo "[regression] set PYTHON_BIN or install pytest before running this suite" >&2
  exit 1
fi

echo "[regression] python compile check"
PYTHONPYCACHEPREFIX=/tmp/python-pycache "$PYTHON_BIN" -m compileall backend/app backend/tests >/dev/null

echo "[regression] backend pytest"
PYTHONPATH=. "$PYTHON_BIN" -m pytest -q backend/tests

if [[ "${SKIP_FRONTEND:-0}" == "1" ]]; then
  echo "[regression] skipping frontend tests (SKIP_FRONTEND=1)"
  echo "[regression] completed"
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[regression] npm is not installed; cannot run frontend test stages" >&2
  exit 1
fi

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
