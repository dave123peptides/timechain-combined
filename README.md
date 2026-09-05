# TimeChain Peptides — Pens (TCP)

The TimeChain Peptides storefront for **pre-filled 3 mL auto-injector
pens**. Forked on 2026-09-05 from the lyophilized-vial storefront
(`~/Desktop/timechain`, `timechain-storefront` on GitHub) as an independent
project: same brand, cart, three-step checkout, Venmo/Zelle manual payment
and Google Sheets order feed, with a pens-only catalog. The vial repo is
not touched by anything in here. Decisions and the side-by-side setup are
recorded in [`docs/plans/pens-fork.md`](docs/plans/pens-fork.md).

**Status:** local storefront complete (34 products, 51 pens, renders for
28 of them); deployment to its own Vercel projects still to do.

## Running it locally (native, side by side with the vial site)

The vial site owns ports 3000/8000 and the `timechain` database; this one
uses 3100/8100 and `tcp`.

```sh
# once: databases (Postgres.app, role timechain), venv, node modules
PG=/Applications/Postgres.app/Contents/Versions/latest/bin
$PG/createdb -h localhost -U postgres -O timechain tcp
$PG/createdb -h localhost -U postgres -O timechain tcp_test
cd services/api && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]" pillow && cd ../..
cd apps/web && npm ci && cd ../..

# .env at the repo root (copied from the vial site, edited: DB tcp, ports
# 8100/3100, same Google Sheets values) and apps/web/.env.local
# (NEXT_PUBLIC_API_BASE_URL, API_INTERNAL_BASE_URL, ADMIN_BASIC_AUTH_*,
# SITE_ACCESS_PASSWORD) — next dev does not read the root .env.

cd services/api
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_pen_catalog      # idempotent; the catalog's source of truth
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100

cd apps/web
npm run dev -- -p 3100                                # http://localhost:3100 (gate password in .env.local)
```

Checks: `services/api/.venv/bin/python -m pytest -q` (against `tcp_test`
via `DATABASE_URL=...`), `npm run lint && npm run typecheck && npm run build`
in `apps/web`.

## Structure

```
apps/web            Next.js + TypeScript frontend
services/api         FastAPI + SQLAlchemy + Alembic backend
services/worker      Python background worker
infra/terraform      Terraform for AWS (ECS/Fargate, RDS, Secrets Manager, SQS)
scripts              Local dev / ops helper scripts
docs                 Architecture and other reference docs
```

See [`docs/architecture.md`](docs/architecture.md) for more detail.

## Prerequisites

- Docker + Docker Compose
- Node.js 22+ (only needed for running `apps/web` outside Docker)
- Python 3.12+ (only needed for running `services/api` / `services/worker` outside Docker)

## Local development

1. Copy the environment template and review it:

   ```sh
   cp .env.example .env
   ```

   `.env` is git-ignored. Never put real secrets in `.env.example` or
   anywhere else in source control — use AWS Secrets Manager for deployed
   environments.

2. Start the full stack:

   ```sh
   docker compose up --build
   ```

   Or use the helper script, which copies `.env.example` for you if `.env`
   doesn't exist yet:

   ```sh
   ./scripts/dev-up.sh
   ```

3. Services:

   | Service | URL                          |
   | ------- | ----------------------------- |
   | Web     | http://localhost:3000          |
   | API     | http://localhost:8000          |
   | API health check | http://localhost:8000/healthz |
   | Postgres | localhost:5432                |

4. Run database migrations (once models exist):

   ```sh
   ./scripts/migrate.sh
   ```

## Running services individually

### Web (`apps/web`)

```sh
cd apps/web
npm install
npm run dev
```

### API (`services/api`)

```sh
cd services/api
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### Worker (`services/worker`)

```sh
cd services/worker
pip install -e ".[dev]"
python -m worker.main
```

## Security

- Never commit real API keys, passwords, or connection strings. Use
  `.env` locally (git-ignored) and AWS Secrets Manager in deployed
  environments.
- `.env.example` documents required variables with placeholder values
  only.
