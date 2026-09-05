# Architecture

TimeChain Peptides is a monorepo containing the frontend, backend API,
background worker, and infrastructure-as-code for the application.

## Components

| Component            | Path                 | Stack                                  |
| --------------------- | --------------------- | --------------------------------------- |
| Web frontend          | `apps/web`            | Next.js, TypeScript                     |
| API                    | `services/api`        | Python, FastAPI, SQLAlchemy, Alembic    |
| Background worker      | `services/worker`     | Python                                  |
| Database               | —                      | PostgreSQL (AWS RDS in deployed envs)   |
| Infrastructure-as-code | `infra/terraform`      | Terraform (AWS ECS/Fargate, RDS, Secrets Manager, SQS) |

## Local development

Local development runs everything via `docker-compose.yml` at the repo
root: a Postgres container, the FastAPI app, the worker, and the Next.js
app. See the root `README.md` for setup steps.

## Deployed environments

In deployed environments:

- `apps/web` and `services/api`/`services/worker` run as containers on
  **AWS ECS/Fargate**.
- The database is **AWS RDS PostgreSQL**.
- Secrets (DB credentials, third-party API keys) are stored in **AWS
  Secrets Manager** and injected into tasks at runtime — never committed to
  source control.
- The worker will eventually consume jobs from **AWS SQS** instead of
  polling.
- CI/CD is handled by **GitLab CI/CD**.

## Status

This is an early scaffold. No business/domain logic has been implemented
yet — the goal so far is a working skeleton with the right shape.
