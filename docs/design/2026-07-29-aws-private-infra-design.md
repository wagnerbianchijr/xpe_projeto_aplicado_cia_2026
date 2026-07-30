# AWS Private Infrastructure — Design (2026-07-29)

Evolução da infraestrutura de rede: **instâncias privadas com NAT + ALB** para exposição segura do dashboard.

## Contexto

Versão anterior (`2026-07-02`) colocava EC2s (PLC + web-system) em **subnets públicas** com IP público. Problemas:
- Custo desnecessário (NAT não era usado, mas instâncias expostas).
- Segurança: banco de dados em subnet privada, mas aplicações web em pública.
- Assimetria arquitetural.

**Objetivo:** Instâncias privadas com acesso à internet via **NAT Gateway** para bootstrap (`pip install`, SSM agent). Dashboard exposto via **ALB** em HTTPS pública.

## Arquitetura

```
┌─ AWS us-east-1 ────────────────────────────────────────────┐
│                                                             │
│  ┌─ Subnet Pública (IGW) ──────────────────────────┐      │
│  │                                                  │      │
│  │  ┌─ NAT Gateway (EIP) ─ Elastic IP             │      │
│  │  │  ↓                                            │      │
│  │  │  • EC2-PLC               ✗ (moved to private)│      │
│  │  │  • EC2-web               ✗ (moved to private)│      │
│  │  │  • ALB 443 ✓             (new, stays public) │      │
│  │  │                                              │      │
│  │  └──────────────────────────────────────────────┘      │
│  │            ↓ route table public (0.0.0.0/0 → IGW)       │
│  └─────────────────────────────────────────────────┘      │
│            ↓                                               │
│  ┌─ Subnet Privada (NAT) ──────────────────────────┐      │
│  │  ↑ route table private (0.0.0.0/0 → NAT GW)    │      │
│  │                                                  │      │
│  │  ✓ EC2-PLC (simulador)                          │      │
│  │  ✓ EC2-web (FastAPI + Caddy)                   │      │
│  │                                                  │      │
│  └──────────────────────────────────────────────────┘      │
│            ↓ (route to Tiger via peering)                  │
│  ┌─ VPC Peering ────────────────────────────────────┐      │
│  │  Tiger Cloud VPC: 11.0.0.0/16                   │      │
│  │  x5mgo2i0fb (TimescaleDB)                       │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Componentes Principais

### 1. NAT Gateway

**Arquivo:** `network.tf`

- **Elastic IP** em subnet pública (alocado na criação).
- **NAT Gateway** anexado à subnet pública.
- **Route table privada** com rota default `0.0.0.0/0 → nat_gateway_id`.
- **Custo:** $0.045/hora + $0.045/GB de dados (saída).

**Por que?** EC2s em subnets privadas precisam de acesso à internet para:
- Baixar pacotes pip (user_data bootstrap).
- Acessar SSM agent (AWS Systems Manager).
- Acessar S3 (download de código).

Sem NAT, essas operações falhariam.

### 2. Instâncias Privadas

**Arquivos:** `plc.tf`, `web.tf`

**Mudanças:**
- `subnet_id = aws_subnet.private[0].id` (era `aws_subnet.public[0].id`)
- `associate_public_ip_address = false` (não tem IP público).

**Implicações:**
- Acesso via **SSM Session Manager** (AWS Systems Manager) — sem SSH key necessária.
- Sem exposição direta à internet — mais seguro.
- Saída à internet controlada pelo NAT.

### 3. Application Load Balancer (ALB)

**Arquivo:** `loadbalancer.tf` (novo)

**Componentes:**
- **Security Group ALB:** ingress 80/443 público, egress para VPC CIDR.
- **ALB:** listeners em 80 (redirect → 443) e 443 (HTTPS).
- **Target Group:** porta 443 HTTPS, health check em `/`.
- **Targets:** instância `web-system` (porta 443, Caddy self-signed).
- **TLS:** certificate auto-assinado (`tls_private_key` + `tls_self_signed_cert`), válido 10 anos, CN=serra-clara.local.

**Custo:** $0.0225/hora + $0.006/LCU (Load Capacity Unit).

**Por que?** 
- EC2 está em subnet privada (sem IP público).
- ALB fornece nome DNS público (`serra-clara-alb-*.elb.amazonaws.com`).
- Redirecionamento HTTP → HTTPS automático.
- Health checks mantêm o target saudável.

### 4. Caddy (HTTPS Reversa)

**Template:** `templates/web_user_data.sh.tftpl`

**Mudanças:**
- Cert self-signed agora usa `localhost` (não IP público).
- CN: `serra-clara.local`; SAN: `localhost`, `serra-clara.local`, `127.0.0.1`.
- Sem dependência de IMDS (`http://169.254.169.254`) — removido, pois EC2 privado não tem acesso garantido.

**Config Caddy:**
```
:443 {
  tls /etc/caddy/cert.pem /etc/caddy/key.pem
  reverse_proxy 127.0.0.1:8000
}
```

Uvicorn roda em `127.0.0.1:8000` (loopback); Caddy escuta `0.0.0.0:443`.

## Fluxo de Tráfego

1. **Usuário** → `https://serra-clara-alb-....elb.amazonaws.com/`
2. **ALB (público)** → health check `/` → target group.
3. **Target Group** → EC2-web (subnet privada) porta 443.
4. **Caddy (443)** → reverse proxy → Uvicorn (8000, loopback).
5. **FastAPI (8000)** → query Tiger via peering (10.20.0.0/16 → 11.0.0.0/16).

Saída do EC2 (pip, SSM, S3) flui por **NAT Gateway** (subnet pública).

## Variáveis de Controle

| Variável | Default | Uso |
|---|---|---|
| `plc_enabled` | `false` | Provisiona EC2-PLC (atual: desabilitado para economizar) |
| `web_enabled` | `false` | Provisiona EC2-web (atual: desabilitado para economizar) |
| ALB (`alb_enabled`) | `false` | Provisiona ALB (atual: desabilitado, sem instâncias web) |

**Status 2026-07-29:** Ambos desabilitados. VPC + peering mantêm (sem custo). Redeploy: ativar flags + `terraform apply`.

## Segurança

- **EC2s privadas:** sem IP público direto, acesso via SSM Session Manager.
- **Database:** subnet privada, acesso privado via peering (não exposição pública).
- **ALB:** security group restringe ingress a 80/443; egress para VPC CIDR.
- **IMDS:** removido do user_data (não confiável em subnet privada).
- **Root volume:** criptografado (`root_block_device { encrypted = true }`).
- **Metadata:** IMDSv2 obrigatório (`http_tokens = "required"`).

## Custagem

**Provisionado:**
- NAT Gateway: $0.045/h (32.4/mês) + dados.
- ALB: $0.0225/h (16.2/mês) + LCU.
- EC2 t3.micro: $0.0104/h (7.5/mês) cada.
- **Total:** ~$75/mês (com 2 EC2s rodando).

**Desabilitado (atual):**
- $0/mês (VPC grátis, peering grátis).

## Redeploy

```bash
# 1. Ativar instâncias
terraform.tfvars:
  plc_enabled = true
  web_enabled = true

# 2. Aplicar
terraform apply

# 3. Aguardar (~5-10 min)
#    - Status checks na EC2.
#    - User_data executa (pip, download código, systemd).
#    - ALB registra targets como healthy.

# 4. Acessar
#    - Dashboard: https://serra-clara-alb-....elb.amazonaws.com/
#    - PLC logs: aws ssm start-session --target <id>
```

## Referências

- Terraform AWS provider: EC2, NAT Gateway, ALB, TLS.
- AWS best practices: private subnets for compute, NAT for egress, ALB for ingress.
- RFC: Certificate SAN, self-signed TLS (non-prod).
