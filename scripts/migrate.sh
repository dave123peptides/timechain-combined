#!/usr/bin/env bash
# Run Alembic migrations against the running `api` container's database.
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose exec api alembic upgrade head
