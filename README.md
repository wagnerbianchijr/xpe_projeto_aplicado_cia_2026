# Serra Clara Bebidas — Solução IIoT na Nuvem

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-TimescaleDB-336791?logo=postgresql&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-EC2%20%C2%B7%20VPC-232F3E?logo=amazonwebservices&logoColor=white)
![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-dashboard-009688?logo=fastapi&logoColor=white)
![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-brightgreen)
![Terraform CI](https://github.com/wagnerbianchijr/xpe_projeto_aplicado_cia_2026/actions/workflows/terraform.yml/badge.svg)

Projeto Aplicado do curso **Cloud Computing com Inteligência Artificial (XPE)**.

Uma solução de nuvem que coleta dados de sensores **IIoT** de uma fábrica de bebidas
fictícia (**Serra Clara Bebidas S.A.**), armazena a série temporal em **TimescaleDB**
no **Tiger Cloud** e expõe indicadores operacionais e históricos em um **dashboard web**.
A infraestrutura (rede + computação) é provisionada com **Terraform** na **AWS**, com
conexão privada ao banco via **VPC peering**.

A arquitetura é **inspirada em sistemas SCADA** (*Supervisory Control and Data
Acquisition*), comuns na indústria, com três camadas: **aquisição de dados de campo**
(o EC2-PLC rodando o simulador, no papel de PLC/RTU que emite as leituras dos sensores),
**dados/histórico** (TimescaleDB no Tiger Cloud, com agregados contínuos) e **supervisão**
(o dashboard web, que apresenta os indicadores em tempo real e o histórico).

## Arquitetura

```
   ┌─────────────────────────── AWS VPC (10.20.0.0/16) ───────────────────────────┐
   │                                                                               │
   │   EC2 "PLC"  ──(grava)──┐                          ┌──(lê)──  EC2 web-system  │
   │   (simulador)           │                          │          (dashboard 443) │
   │                         ▼        VPC peering        ▼                         │
   │                    ╔═══════════════════════════════════╗                     │
   └────────────────────╢  Tiger Cloud — TimescaleDB (priv.) ╟─────────────────────┘
                        ╚═══════════════════════════════════╝
                                                              usuários ── HTTPS 443
                                                              (navegador)

   Terraform provisiona: VPC, subnets, VPC peering ao Tiger e os 2 EC2.
```

Fluxo ponta a ponta: o **simulador** (no EC2-PLC) gera leituras e grava na hypertable →
**agregados contínuos** e **views** derivam os indicadores → o **web-system** (no EC2
público) lê e renderiza o dashboard. O banco é privado, acessível apenas pela VPC
(peering); o dashboard é público em HTTPS/443.

## Componentes

| Componente | Descrição | Documentação |
|---|---|---|
| **modelo-de-dados** | Schema TimescaleDB: dimensões, hypertable `sensor_reading`, agregados contínuos (1m/15m/30m/1h), views de apoio e seed (3 linhas / 30 sensores). | [modelo-de-dados/README.md](modelo-de-dados/README.md) |
| **simulador** | Gerador IIoT em Python (random walk + anomalias + dropouts) que grava leituras no banco. Roda como serviço no EC2-PLC. | [simulador/README.md](simulador/README.md) |
| **web-system** | Dashboard em FastAPI + HTMX + Chart.js: visão geral (KPIs + esteiras por linha), Operational Hub, Performance Insights e detalhe do sensor. | [web-system/README.md](web-system/README.md) |
| **terraform** | Infra AWS: VPC, subnets, VPC peering ao Tiger e os EC2 (PLC + web-system público em 443). | [terraform/README.md](terraform/README.md) |

## Stack

- **Banco:** TimescaleDB (PostgreSQL) no Tiger Cloud (AWS us-east-1).
- **Simulador:** Python 3 (psycopg 3, python-dotenv).
- **Web:** FastAPI, HTMX, Chart.js, Jinja2, Uvicorn; Caddy (TLS) no EC2.
- **Infra:** Terraform (provider AWS), AWS EC2/VPC/SSM/S3, VPC peering.
- **CI:** GitHub Actions — Terraform `fmt`/`validate` + Trivy, e Infracost (custo + tagging policy) nos PRs. Veja [`.github/workflows/`](.github/workflows).

## Documentação de projeto

- **Especificações de design:** [`docs/design/`](docs/design)
  - [modelo-de-dados](docs/design/2026-07-01-modelo-de-dados-design.md) ·
    [simulador](docs/design/2026-07-01-simulador-design.md) ·
    [web-system](docs/design/2026-07-01-web-system-design.md) ·
    [terraform (AWS + peering)](docs/design/2026-07-02-terraform-aws-design.md) ·
    [EC2 do web-system](docs/design/2026-07-03-web-system-ec2-design.md) ·
    [esteiras na visão geral](docs/design/2026-07-03-esteiras-visao-geral-design.md)
- **Planos de implementação:** [`docs/plans/`](docs/plans)

## Como executar

Cada componente tem instruções detalhadas no seu README. Resumo:

1. **Banco** — aplicar o schema no serviço Tiger Cloud (ver [modelo-de-dados](modelo-de-dados/README.md)).
2. **Infra** — `cd terraform && terraform init && terraform apply` provisiona VPC, peering
   e os EC2 (o PLC sobe o simulador e o EC2 web sobe o dashboard automaticamente). Ver
   [terraform](terraform/README.md).
3. **Local (opcional)** — o `simulador` e o `web-system` também rodam localmente contra o
   banco (com um `.env` próprio); ver os READMEs de cada um.

## Custos

A infra tem componentes gratuitos (VPC, subnets, peering) e pagos (os 2 EC2 + EBS + IPv4;
o serviço Tiger Cloud). Para **parar tudo que gera custo**: `plc_enabled=false` e
`web_enabled=false` no `terraform.tfvars` + `terraform apply` (remove os EC2), e pausar o
serviço no Tiger Cloud. Detalhes em [terraform/README.md](terraform/README.md).

## Convenções

- Segredos ficam apenas em arquivos `.env` (git-ignored); nunca são commitados.
- SQL formatado com vírgula à esquerda; comentários e docstrings em português.
