#!/usr/bin/env bash
# Local development: API on :8000 (SQLite by default) and web on :3000.
# Usage: scripts/dev.sh            (Ctrl+C stops both)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

export IIOS_ENVIRONMENT="${IIOS_ENVIRONMENT:-development}"
export IIOS_COOKIE_SECURE="${IIOS_COOKIE_SECURE:-false}"   # plain HTTP on localhost
export IIOS_LOG_JSON="${IIOS_LOG_JSON:-false}"

cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-dev.txt
fi
.venv/bin/python -m app.cli migrate

cd "$ROOT/frontend"
[ -d node_modules ] || npm ci --no-audit --no-fund

trap 'kill 0' EXIT
(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
(cd "$ROOT/frontend" && IIOS_BACKEND_URL=http://127.0.0.1:8000 npm run dev) &
echo "API: http://127.0.0.1:8000/api/v1/docs  ·  Web: http://127.0.0.1:3000"
echo "Primera vez: crea una organización con  cd backend && .venv/bin/python -m app.cli create-org --name ... --admin-email ... --admin-name ..."
wait
