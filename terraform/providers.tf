provider "aws" {
  profile = var.aws_profile
  region  = var.aws_region

  # Tags aplicadas a todos os recursos taggáveis. Service + Environment atendem
  # à tagging policy FinOps do Infracost (Environment ∈ {Dev, Stage, Prod}).
  # Environment é um LITERAL (não var): o Infracost sequestra variáveis chamadas
  # "environment", resolvendo-as para o nome do branch (ex.: "main") em vez do
  # default — o que reprovaria a policy. Um literal evita isso.
  default_tags {
    tags = {
      Service     = var.service
      Environment = "Prod"
      Project     = var.project
      Component   = "terraform"
      ManagedBy   = "terraform"
    }
  }
}
