terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state backend (S3 + DynamoDB lock table) to be configured once
  # the target AWS account/bucket exist. Left unset intentionally so this
  # scaffold never points at real infrastructure by accident.
  #
  # backend "s3" {
  #   bucket         = "timechain-terraform-state"
  #   key            = "timechain/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "timechain-terraform-locks"
  #   encrypt        = true
  # }
}
