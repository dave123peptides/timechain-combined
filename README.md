# TimeChain Peptides

Custom ecommerce application. This repo is a monorepo containing the
frontend, API, background worker, and infrastructure-as-code.

**Status:** early scaffold — no business logic yet.

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
