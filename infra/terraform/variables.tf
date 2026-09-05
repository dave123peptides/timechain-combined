variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (e.g. dev, staging, prod)."
  type        = string
  default     = "dev"
}

# No resources are defined yet — modules for ECS/Fargate, RDS PostgreSQL,
# Secrets Manager, and SQS will be added here as infrastructure work
# begins. This file exists to establish the module's variable surface
# ahead of that work.
