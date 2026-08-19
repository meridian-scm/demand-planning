#!/usr/bin/env bash
# Resets the database schema (via Alembic) and reloads deterministic demo
# data. Safe to re-run at any time during local development.
set -euo pipefail

cd "$(dirname "$0")/../backend"

echo "==> Running Alembic migrations"
alembic upgrade head

echo "==> Seeding demo data"
python -m app.seed.cli

echo "==> Done. Start the API with: uvicorn app.main:app --reload"
