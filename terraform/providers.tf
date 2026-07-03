provider "aws" {
  profile = var.aws_profile
  region  = var.aws_region

  # Tags aplicadas a todos os recursos taggáveis. Service + Environment atendem
  # à tagging policy FinOps do Infracost (Environment ∈ {Dev, Stage, Prod}).
  default_tags {
    tags = {
      Service     = var.service
      Environment = var.environment
      Project     = var.project
      Component   = "terraform"
      ManagedBy   = "terraform"
    }
  }
}
