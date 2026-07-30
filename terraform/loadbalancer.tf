# Application Load Balancer para expor web-system em HTTPS
# O web-system roda em HTTP/8000 internamente e Caddy faz HTTPS/443 local.
# ALB recebe tráfego público na 443 e encaminha para web-system via IP privado.

locals {
  alb_enabled = false # Desabilitado para economizar (sem instâncias web rodando)
}

# Security Group para ALB
resource "aws_security_group" "alb" {
  count       = local.alb_enabled ? 1 : 0
  name        = "${var.project}-alb-sg"
  description = "ALB: inbound 443 publico + saida"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS public"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP public (redirect to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Outbound to private subnets"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = { Name = "${var.project}-alb-sg" }
}

# ALB
resource "aws_lb" "main" {
  count              = local.alb_enabled ? 1 : 0
  name               = "${var.project}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb[0].id]
  subnets            = aws_subnet.public[*].id

  tags = { Name = "${var.project}-alb" }
}

# Target Group
resource "aws_lb_target_group" "web" {
  count       = local.alb_enabled ? 1 : 0
  name        = "${var.project}-web-tg"
  port        = 443
  protocol    = "HTTPS"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 3
    interval            = 30
    path                = "/"
    matcher             = "200"
    protocol            = "HTTPS"
  }

  tags = { Name = "${var.project}-web-tg" }
}

# Register web instance no target group
resource "aws_lb_target_group_attachment" "web" {
  count            = local.alb_enabled ? 1 : 0
  target_group_arn = aws_lb_target_group.web[0].arn
  target_id        = aws_instance.web[0].id
  port             = 443
}

# HTTPS Listener (self-signed cert gerado pela instância Caddy)
# Para produção, usar certificate.pem do ACM.
resource "aws_lb_listener" "https" {
  count             = local.alb_enabled ? 1 : 0
  load_balancer_arn = aws_lb.main[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.self_signed[0].arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web[0].arn
  }
}

# HTTP Listener (redireciona para HTTPS)
resource "aws_lb_listener" "http" {
  count             = local.alb_enabled ? 1 : 0
  load_balancer_arn = aws_lb.main[0].arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# Self-signed certificate para ALB (válido por 365 dias)
resource "tls_private_key" "self_signed" {
  count     = local.alb_enabled ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "self_signed" {
  count                 = local.alb_enabled ? 1 : 0
  private_key_pem       = tls_private_key.self_signed[0].private_key_pem
  validity_period_hours = 8760

  subject {
    common_name  = "serra-clara.local"
    organization = "Serra Clara Bebidas"
  }

  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "server_auth",
  ]
}

resource "aws_acm_certificate" "self_signed" {
  count            = local.alb_enabled ? 1 : 0
  private_key      = tls_private_key.self_signed[0].private_key_pem
  certificate_body = tls_self_signed_cert.self_signed[0].cert_pem

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${var.project}-self-signed-cert" }
}

# Output ALB DNS name
output "alb_dns_name" {
  value       = try(aws_lb.main[0].dns_name, "")
  description = "DNS name do ALB (acesso ao web-system)"
}

output "alb_url" {
  value       = try("https://${aws_lb.main[0].dns_name}/", "")
  description = "URL para acessar web-system via ALB"
}
