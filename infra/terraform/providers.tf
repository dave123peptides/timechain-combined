provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "timechain-peptides"
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}
