# infra/terraform

Terraform root module for TimeChain Peptides AWS infrastructure.

**Status:** scaffold only — no resources are provisioned yet.

## Planned layout

As infrastructure work begins, this will grow into modules for:

- `ecs/` — ECS/Fargate cluster, services, and task definitions for `services/api` and `services/worker`
- `rds/` — RDS PostgreSQL instance
- `secrets/` — AWS Secrets Manager entries (DB credentials, API keys)
- `sqs/` — SQS queue(s) consumed by `services/worker`
- `networking/` — VPC, subnets, security groups

## Remote state

A remote state backend (S3 + DynamoDB lock table) is stubbed out but
commented in `versions.tf`. It should be uncommented and pointed at a real
bucket/table before any `terraform apply` is run against a shared
environment.

## Usage

```sh
terraform init
terraform plan
```

No `terraform apply` should be run until real resources are defined.
