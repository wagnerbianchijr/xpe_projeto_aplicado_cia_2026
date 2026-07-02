provider "aws" {
  profile = var.aws_profile
  region  = var.aws_region

  default_tags {
    tags = {
      project     = var.project
      environment = var.environment
      component   = "terraform"
      managed_by  = "terraform"
    }
  }
}
