# AWS Deployment Plan — 2026-07-29

## Objetivo

Provisionar infraestrutura AWS para a solução IIoT da Serra Clara Bebidas S.A. com instâncias privadas, NAT Gateway, e exposição pública via Application Load Balancer.

## Estado Final Desejado

**Infraestrutura em AWS (us-east-1):**
- VPC privada (`10.20.0.0/16`) conectada ao Tiger Cloud via peering.
- EC2-PLC (simulador) em subnet privada, gerando dados IIoT.
- EC2-web (FastAPI + Caddy) em subnet privada, dashboard exposto via HTTPS/ALB.
- NAT Gateway para saída à internet (pip, SSM, S3).
- Application Load Balancer (HTTPS 443 público) → targets privados.

**Database:**
- TimescaleDB em Tiger Cloud (`x5mgo2i0fb.tgqtelaqv0.vpc.tsdb.forge.timescale.com:5432`).
- Acesso privado via peering VPC.

## Fases de Execução

### Fase 1: Infraestrutura Base

**O quê:**
- VPC + subnets (públicas/privadas).
- Internet Gateway.
- Route tables (pública → IGW; privada → NAT).
- VPC peering com Tiger Cloud (aceitação de pedido + rotas).

**Como:**
```bash
terraform apply
# Preencher terraform.tfvars com tiger_peering_connection_id (obtido do Tiger Console)
```

**Saídas críticas:**
- `aws_account_id`
- `vpc_id`
- `peering_connection_state` (deve ser "active")

---

### Fase 2: Instâncias EC2

**Pré-requisito:**
- SSM Parameter Store com DATABASE_URL preenchido:
  ```bash
  aws ssm put-parameter --name /serra-clara/plc/database_url \
    --value "postgresql://tsdbadmin:PASS@x5mgo2i0fb.tgqtelaqv0.vpc.tsdb.forge.timescale.com:5432/tsdb?sslmode=require" \
    --type SecureString --region us-east-1
  ```

**O quê:**
- EC2-PLC (subnet privada) com user_data que:
  - Instala Python 3.11.
  - Baixa simulador do S3.
  - Cria venv, `pip install`.
  - Lê DATABASE_URL do SSM.
  - Sobe serviço `plc.service` (systemd, auto-restart).
- EC2-web (subnet privada) com user_data que:
  - Instala Python 3.11, Caddy.
  - Baixa web-system do S3.
  - Cria venv, `pip install`.
  - Lê DATABASE_URL do SSM.
  - Gera cert self-signed (CN=serra-clara.local).
  - Sobe serviço `websystem.service` + `caddy.service`.

**Como:**
```bash
# terraform.tfvars
plc_enabled = true
web_enabled = true

terraform apply
```

**Saídas críticas:**
- `plc_instance_id` (ex: `i-085368e955b569917`)
- `web_instance_id`
- `plc_ssm_start_command` — para debug via SSM

**Tempo:** ~10 min (status checks + user_data).

---

### Fase 3: ALB (Exposição Pública)

**O quê:**
- Application Load Balancer em subnets públicas.
- Security Group (ingress 80/443 público, egress VPC).
- Target Group (porta 443 HTTPS, health check `/`).
- Listeners:
  - 80 → 301 redirect HTTPS.
  - 443 → targets (EC2-web).
- TLS: certificate auto-assinado (10 anos).

**Como:**
```bash
# terraform.tfvars
alb_enabled = true  # se necessário (default false em 2026-07-29)

terraform apply
```

**Saída crítica:**
- `alb_dns_name` (ex: `serra-clara-alb-....elb.amazonaws.com`)

**Acesso:**
```bash
curl -sk https://serra-clara-alb-....elb.amazonaws.com/
```

---

## Verificação End-to-End

### 1. VPC & Peering
```bash
# Peering status
aws ec2 describe-vpc-peering-connections \
  --vpc-peering-connection-ids pcx-0107700b1842f5a47 \
  --region us-east-1 | grep State
# Esperado: "active"

# Route table privada
aws ec2 describe-route-tables \
  --filters Name=tag:Name,Values=serra-clara-private-rt \
  --region us-east-1 | grep -A2 DestinationCidrBlock
# Esperado: rotas para 0.0.0.0/0 (NAT) e 11.0.0.0/16 (Tiger)
```

### 2. Instâncias EC2
```bash
# Status de health checks
aws ec2 describe-instance-status \
  --instance-ids i-085368e955b569917 \
  --region us-east-1 | grep Status
# Esperado: ok (após ~5 min)

# Verificar serviços
aws ssm start-session --target i-085368e955b569917 --region us-east-1
# Na instância: systemctl status plc ; journalctl -u plc -f
```

### 3. Conectividade com Database
```bash
# Da instância PLC, testar conexão
/opt/plc/.venv/bin/python3 << EOF
import psycopg
conn = psycopg.connect("postgresql://tsdbadmin:PASS@x5mgo2i0fb.tgqtelaqv0.vpc.tsdb.forge.timescale.com:5432/tsdb?sslmode=require")
print(conn.info)
conn.close()
EOF
# Esperado: conexão bem-sucedida
```

### 4. ALB & Dashboard
```bash
# Health check status
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:...:targetgroup/serra-clara-web-tg/... \
  --region us-east-1 | grep State
# Esperado: healthy

# Acessar dashboard
curl -sk https://serra-clara-alb-....elb.amazonaws.com/
# Esperado: HTML com "Serra Clara Bebidas — Painel IIoT"
```

---

## Deprovisionar (Economizar Custos)

Para parar instâncias e ALB (VPC + peering permanecem):

```bash
# terraform.tfvars
plc_enabled = false
web_enabled = false
alb_enabled = false  # (se ativado antes)

terraform apply
# Confirma destruição
```

**Custo:** VPC + peering = $0/mês (ambos grátis).

Redeploy rápido: ativar flags + `terraform apply` (~15 min).

---

## Troubleshooting

| Problema | Verificação | Solução |
|---|---|---|
| EC2 status checks falhando | `aws ec2 describe-instance-status` | Aguardar 5+ min; verificar security group (egress liberado) |
| PLC não conecta ao Tiger | `journalctl -u plc -f` via SSM | Verificar DATABASE_URL em SSM; testar DNS (ponte de peering) |
| ALB target unhealthy | `aws elbv2 describe-target-health` | Verificar Caddy em port 443; security group do ALB (egress VPC) |
| NAT Gateway não criando | `terraform plan` | Verificar se há ENIs presas; aguardar remoção de recursos antigos |

---

## Referências

- Design: [`docs/design/2026-07-29-aws-private-infra-design.md`](../design/2026-07-29-aws-private-infra-design.md)
- Terraform: [`terraform/README.md`](../../terraform/README.md)
- Tiger Cloud: VPC Peering (AWS) — https://www.tigerdata.com/docs/deploy/tiger-cloud/tiger-cloud-aws/security/vpc
