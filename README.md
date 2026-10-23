# TimeChain Peptides, combined storefront (pens + vials)

The TimeChain Peptides storefront for **both** product lines: pre-filled
3 mL auto-injector pens and lyophilized vials, one product page per
compound with a Pen | Vial picker and a Pens | Vials toggle over the
catalog. Forked on 2026-10-22 from the pens site (`~/Desktop/TCP`,
buytcp.com), itself a 2026-09-05 fork of the vial site
(`~/Desktop/timechain`, www.timechainpeptides.com). Neither ancestor is
touched by anything in here. The plan, David's decisions and the launch
runbook are in [`docs/plans/combined-site-plan.md`](docs/plans/combined-site-plan.md)
and [`docs/plans/combined-site-launch.md`](docs/plans/combined-site-launch.md).

**This site takes no payments** (David, 2026-10-22). It is a showcase:
visitors browse the catalog and book a meeting from `/contact`. The
cart, checkout and payment providers inherited from the pens site are
still in the tree behind two switches that are off by default:
`ORDERING_ENABLED` on the API (checkout writes answer 503, the catalog is
unaffected) and `NEXT_PUBLIC_ORDERING_ENABLED` on the web (no cart
drawer, no Add to Cart; `/cart` and `/checkout` redirect to `/contact`).

**Status:** local storefront complete (41 products: 52 pens + 48 vials,
29 compounds in both formats, every product has a photo); deployment to
its own Vercel projects and the domain move are still to do (runbook
above). The scheduling link for the Book a meeting button
(`NEXT_PUBLIC_BOOKING_URL`) is still to come from David; until it is set
the button is an email.

## Running it locally (native, side by side with the other two sites)

The vial site owns ports 3000/8000 and the `timechain` database, the pens
site 3100/8100 and `tcp`; this one reuses 3100/8100 (run one at a time)
with the `tcp_combined` database.

```sh
# once: databases (Postgres.app, role timechain), venv, node modules
PG=/Applications/Postgres.app/Contents/Versions/latest/bin
$PG/createdb -h localhost -U postgres -O timechain tcp_combined
$PG/createdb -h localhost -U postgres -O timechain tcp_combined_test
cd services/api && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]" pillow && cd ../..
cd apps/web && npm ci && cd ../..

# .env at the repo root (DB tcp_combined, ports 8100/3100) and
# apps/web/.env.local (NEXT_PUBLIC_API_BASE_URL, API_INTERNAL_BASE_URL,
# ADMIN_BASIC_AUTH_*, SITE_ACCESS_PASSWORD). next dev does not read the
# root .env.

cd services/api
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_pen_catalog      # idempotent; pens
.venv/bin/python -m app.scripts.seed_lyo_catalog      # idempotent; vials (either order, rerun freely)
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100

cd apps/web
npm run dev -- -p 3100                                # http://localhost:3100 (SITE_ACCESS_PASSWORD in .env.local locks it; unset = open)
```

Checks: `DATABASE_URL=...tcp_combined_test services/api/.venv/bin/python -m pytest -q`,
`npm run lint && npm run typecheck && npm run build` in `apps/web`.

Quick API sanity after seeding:

```sh
curl -s 'localhost:8100/shop/products?format=lyophilized' | jq length   # 35
curl -s 'localhost:8100/shop/products?format=pen' | jq length           # 35
curl -s localhost:8100/shop/filter-options                              # formats: lyophilized, pen
```

## Deploying to Vercel

Two new Vercel projects from this repo, a new Neon database, then the
domain moves over from the vial site's `timechain-storefront` project.
Step by step, with the environment variables, in
[`docs/plans/combined-site-launch.md`](docs/plans/combined-site-launch.md).
Never link this repo to `tcp-api` / `tcp-storefront` (pens) or
`timechain-api` / `timechain-storefront` (vials); delete any `.vercel/`
directory carried over from the fork before running `vercel`.

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
