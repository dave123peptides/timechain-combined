#!/usr/bin/env bash
# Vercel build step for the API (vercel.json → buildCommand).
#
# Runs inside Vercel's build container with the project's env vars, so it
# can reach the production database without that URL ever living on a
# dev box: applies pending migrations, then loads the committed
# certificate manifest (data/coa/coa_manifest.csv) into product_coas.
# Both steps are idempotent; the sync never deletes or re-publishes.
#
# Preview builds have no DATABASE_URL (the API's env is Production-only)
# and skip both steps. A failing migration fails the build — better than
# serving code the schema can't back.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${DATABASE_URL:-}" ]; then
  echo "vercel-build: DATABASE_URL not set — skipping migrations and COA sync"
  exit 0
fi

# The app needs Python >= 3.10 syntax; prefer a modern interpreter if the
# build image offers several.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for candidate in python3.12 python3.13 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
  done
fi
echo "vercel-build: using $("$PY" --version 2>&1)"
# Install into a throwaway venv outside the project (PEP 668 "externally
# managed" images refuse bare pip installs, and a venv inside the project
# would be bundled into the function).
if [ -z "${SKIP_PIP:-}" ]; then
  VENV="${TMPDIR:-/tmp}/timechain-api-build-venv"
  # Always rebuild from scratch: a venv restored from Vercel's build cache
  # has proven half-populated (alembic present, sqlalchemy missing) and a
  # stale one fails in ways the log can't explain.
  rm -rf "$VENV"
  "$PY" -m venv "$VENV"
  # PYTHONPATH must be cleared for pip too: with Vercel's runtime package
  # dir on sys.path, pip counts every requirement "already satisfied" and
  # installs nothing into the venv.
  env -u PYTHONPATH "$VENV/bin/pip" install --disable-pip-version-check -r requirements.txt alembic
  PY="$VENV/bin/python"
fi

# Fail here with a clear message rather than mid-migration with a cryptic
# import error.
env -u PYTHONPATH "$PY" -c "import sqlalchemy, alembic, pydantic; print('vercel-build: deps ok')"

echo "vercel-build: alembic upgrade head"
# Vercel exports PYTHONPATH=.vercel_python_packages (runtime packages built
# for the function's Python, e.g. 3.14). Our throwaway venv may be a
# different minor version, and a mismatched compiled pydantic_core there
# crashes the import — so run the DB steps with PYTHONPATH cleared; the
# venv's own site-packages plus the project dir are all they need.
env -u PYTHONPATH "$PY" -m alembic upgrade head
echo "vercel-build: syncing certificate manifest"
env -u PYTHONPATH "$PY" -m app.scripts.sync_coas
