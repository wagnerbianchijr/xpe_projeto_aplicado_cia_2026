data "aws_caller_identity" "current" {}

output "aws_account_id" {
  description = "Conta AWS (informe no Tiger Console ao criar o peering)."
  value       = data.aws_caller_identity.current.account_id
}

output "vpc_id" {
  description = "ID da VPC (informe no Tiger Console ao criar o peering)."
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR da VPC."
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "IDs das subnets públicas."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs das subnets privadas."
  value       = aws_subnet.private[*].id
}

output "db_security_group_id" {
  description = "Security group para clientes que acessam o Tiger via peering."
  value       = aws_security_group.db_egress.id
}

output "peering_connection_state" {
  description = "Estado da conexão de peering (null enquanto não configurada)."
  value       = local.peering_enabled ? aws_vpc_peering_connection_accepter.tiger[0].accept_status : null
}
