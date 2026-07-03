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

output "plc_instance_id" {
  description = "ID da instância EC2-PLC (null quando plc_enabled=false)."
  value       = var.plc_enabled ? aws_instance.plc[0].id : null
}

output "plc_public_ip" {
  description = "IP público do EC2-PLC."
  value       = var.plc_enabled ? aws_instance.plc[0].public_ip : null
}

output "plc_ssm_start_command" {
  description = "Comando para abrir sessão SSM no PLC."
  value       = var.plc_enabled ? "aws ssm start-session --target ${aws_instance.plc[0].id} --region ${var.aws_region} --profile ${var.aws_profile}" : null
}

output "plc_source_bucket" {
  description = "Bucket S3 com o código do simulador entregue ao PLC."
  value       = var.plc_enabled ? aws_s3_bucket.plc_src[0].id : null
}

output "web_instance_id" {
  description = "ID da instância EC2 do web-system (null quando web_enabled=false)."
  value       = var.web_enabled ? aws_instance.web[0].id : null
}

output "web_public_ip" {
  description = "IP público do web-system."
  value       = var.web_enabled ? aws_instance.web[0].public_ip : null
}

output "web_url" {
  description = "URL do dashboard (cert self-signed; aceite o aviso do navegador)."
  value       = var.web_enabled ? "https://${aws_instance.web[0].public_ip}/" : null
}

output "web_ssm_start_command" {
  description = "Comando para abrir sessão SSM no web-system."
  value       = var.web_enabled ? "aws ssm start-session --target ${aws_instance.web[0].id} --region ${var.aws_region} --profile ${var.aws_profile}" : null
}
