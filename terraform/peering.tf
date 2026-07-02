# Conexão privada ao Tiger Cloud via VPC peering.
#
# Fluxo: o Tiger Cloud INICIA o pedido de peering a partir do Tiger Console
# (informando AWS account ID + VPC ID + CIDR + região); a AWS ACEITA o pedido
# (pcx-...), roteia o CIDR do Tiger e libera o security group.
#
# Enquanto tiger_peering_connection_id estiver vazio, os recursos de peering não
# são criados — assim `plan` permanece limpo sem depender do pedido do Tiger.

locals {
  peering_enabled = var.tiger_peering_connection_id != ""
}

resource "aws_vpc_peering_connection_accepter" "tiger" {
  count                     = local.peering_enabled ? 1 : 0
  vpc_peering_connection_id = var.tiger_peering_connection_id
  auto_accept               = true

  tags = { Name = "${var.project}-tiger-peering" }
}

resource "aws_route" "to_tiger_public" {
  count                     = local.peering_enabled ? 1 : 0
  route_table_id            = aws_route_table.public.id
  destination_cidr_block    = var.tiger_peer_cidr
  vpc_peering_connection_id = var.tiger_peering_connection_id
}

resource "aws_route" "to_tiger_private" {
  count                     = local.peering_enabled ? 1 : 0
  route_table_id            = aws_route_table.private.id
  destination_cidr_block    = var.tiger_peer_cidr
  vpc_peering_connection_id = var.tiger_peering_connection_id
}

# Security group para clientes na VPC que acessam o Tiger via peering.
# Só saída, na porta do Postgres, restrita ao CIDR da Peering VPC do Tiger.
resource "aws_security_group" "db_egress" {
  name        = "${var.project}-tiger-db-egress"
  description = "Saida ao Tiger Cloud (Postgres) via VPC peering."
  vpc_id      = aws_vpc.main.id

  egress {
    description = "Postgres para a Peering VPC do Tiger"
    from_port   = var.db_port
    to_port     = var.db_port
    protocol    = "tcp"
    cidr_blocks = [var.tiger_peer_cidr]
  }

  tags = { Name = "${var.project}-tiger-db-egress" }
}
