variable "aws_profile" {
  description = "Perfil da AWS CLI usado pelo provider."
  type        = string
  default     = "bianchi_aws"
}

variable "aws_region" {
  description = "Região AWS (deve casar com o serviço Tiger Cloud)."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR da VPC. Não pode colidir com a Peering VPC do Tiger."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr deve ser um bloco CIDR IPv4 válido."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDRs das subnets públicas (uma por AZ, na mesma ordem de azs)."
  type        = list(string)
  default     = ["10.20.0.0/24", "10.20.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDRs das subnets privadas (uma por AZ, na mesma ordem de azs)."
  type        = list(string)
  default     = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "azs" {
  description = "Zonas de disponibilidade (mesma ordem dos CIDRs de subnet)."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "tiger_peer_cidr" {
  description = "CIDR da Peering VPC do Tiger Cloud."
  type        = string
  default     = "11.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.tiger_peer_cidr, 0))
    error_message = "tiger_peer_cidr deve ser um bloco CIDR IPv4 válido."
  }
}

variable "tiger_peering_connection_id" {
  description = "ID (pcx-...) do pedido de peering criado pelo Tiger. Vazio até existir; quando vazio, os recursos de peering não são criados."
  type        = string
  default     = ""
}

variable "db_port" {
  description = "Porta TCP do Postgres liberada em direção ao Tiger (doc do Tiger: 5432; endpoint público do serviço: 36101)."
  type        = number
  default     = 5432
}

variable "project" {
  description = "Nome do projeto, usado em nomes e tags."
  type        = string
  default     = "serra-clara"
}

variable "environment" {
  description = "Ambiente lógico, usado em tags."
  type        = string
  default     = "demo"
}

variable "plc_enabled" {
  description = "Cria (true) ou não (false) o EC2-PLC e recursos associados."
  type        = bool
  default     = true
}

variable "plc_instance_type" {
  description = "Tipo da instância EC2-PLC."
  type        = string
  default     = "t3.micro"
}

variable "db_url_ssm_param" {
  description = "Nome do parâmetro SSM (SecureString) com o DATABASE_URL do PLC. Criado fora do Terraform."
  type        = string
  default     = "/serra-clara/plc/database_url"
}
