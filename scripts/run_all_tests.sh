#!/usr/bin/env bash
# Runs every automated test layer in this repo and reports a summary.
# Assumes: Python venv set up in backend/, Node available for frontend/e2e,
# and (for the Postgres-specific + E2E suites) `docker compose up -d db`.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

echo "=================================================="
echo "1/3  Backend tests (pytest)"
echo "=================================================="
(cd "$ROOT/backend" && pytest tests -q) || FAILED=1

echo "=================================================="
echo "2/3  Frontend tests (vitest)"
echo "=================================================="
(cd "$ROOT/frontend" && npm test) || FAILED=1

echo "=================================================="
echo "3/3  End-to-end tests (playwright)"
echo "=================================================="
if curl -sf http://localhost:5173 >/dev/null 2>&1; then
  (cd "$ROOT/e2e" && npm test) || FAILED=1
else
  echo "Skipping E2E — stack not running at http://localhost:5173"
  echo "Start it with: docker compose up -d"
fi

echo "=================================================="
if [ "$FAILED" -eq 0 ]; then
  echo "ALL TEST LAYERS PASSED"
else
  echo "ONE OR MORE TEST LAYERS FAILED — see output above"
fi
echo "=================================================="
exit $FAILED
