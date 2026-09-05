#!/usr/bin/env bash
# Start the full local dev stack (db, api, worker, web) via docker-compose.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found — copying .env.example. Review it before continuing." >&2
  cp .env.example .env
fi

docker compose up --build
