# terraform (AWS) — Design

Infraestrutura de rede na AWS para a solução IIoT da **Serra Clara Bebidas S.A.**,
com conexão privada ao serviço Tiger Cloud via **VPC peering**. Último componente
do projeto. Entrega **demonstrativa**: o código passa em `fmt` + `validate` (e
`plan` com credenciais), **sem `apply`** obrigatório.

## Contexto

- Serviço Tiger Cloud de destino: **db-17829** (`x5mgo2i0fb`), AWS **us-east-1**.
- VPC do Tiger (Peering VPC, criada no Tiger Console): CIDR **11.0.0.0/16**.
- Conta/credenciais AWS: profile **`bianchi_aws`**, conta **<AWS_ACCOUNT_ID>**, região **us-east-1**.
- Fluxo de peering do Tiger (AWS): **o Tiger inicia** o pedido de peering a partir do
  Tiger Console (informando AWS account ID + VPC ID + CIDR + região); a **AWS aceita**
  o pedido (`pcx-…`), adiciona a rota para o CIDR do Tiger e libera o security group.

## Provider e escopo

- Provider `aws` (`~> 5.x`), `terraform >= 1.9`.
- `provider "aws" { profile = var.aws_profile, region = var.aws_region }`.
- Sem backend remoto (state local; entrega demonstrativa).
- Alvo de qualidade: `terraform fmt -check` e `terraform validate` limpos (não exigem
  credenciais). `terraform plan` funciona com o profile `bianchi_aws`, mas não é exigido.

## Rede

- VPC `10.20.0.0/16` — **não colide** com o CIDR do Tiger (`11.0.0.0/16`).
- Subnets:
  - públicas: `10.20.0.0/24` (us-east-1a), `10.20.1.0/24` (us-east-1b)
  - privadas: `10.20.10.0/24` (us-east-1a), `10.20.11.0/24` (us-east-1b)
- Internet Gateway + route table pública (`0.0.0.0/0` → IGW) associada às subnets públicas.
- Route table privada associada às subnets privadas (sem rota default; **sem NAT** — custo
  evitado e o acesso ao Tiger é privado via peering).
- Tags padrão em todos os recursos (projeto, ambiente, componente).

## Peering ao Tiger Cloud (parametrizado)

O Tiger inicia; a AWS aceita. O Terraform modela o **lado AWS**:

- `aws_vpc_peering_connection_accepter` — aceita o pedido `pcx-…` criado pelo Tiger
  (`vpc_peering_connection_id = var.tiger_peering_connection_id`, `auto_accept = true`).
- `aws_route` nas route tables (pública e privada): destino `var.tiger_peer_cidr`
  (`11.0.0.0/16`) → `vpc_peering_connection_id`.
- `aws_security_group` permitindo **saída** TCP para `var.tiger_peer_cidr` na porta do
  banco (`var.db_port`), para uso por qualquer computação futura na VPC.

**Guarda de `plan` limpo:** os três recursos acima usam
`count = var.tiger_peering_connection_id != "" ? 1 : 0`. Enquanto o `pcx-` não é
conhecido (padrão `""`), eles não entram no `plan`, que permanece válido e limpo sem
exigir o pedido do Tiger. Ao preencher a variável, o `apply` aceita e roteia o peering.

## Variáveis (`variables.tf`)

| Variável | Tipo | Default | Uso |
|---|---|---|---|
| `aws_profile` | string | `"bianchi_aws"` | perfil da AWS CLI |
| `aws_region` | string | `"us-east-1"` | região (casa com o serviço Tiger) |
| `vpc_cidr` | string | `"10.20.0.0/16"` | CIDR da VPC |
| `public_subnet_cidrs` | list(string) | `["10.20.0.0/24","10.20.1.0/24"]` | subnets públicas |
| `private_subnet_cidrs` | list(string) | `["10.20.10.0/24","10.20.11.0/24"]` | subnets privadas |
| `azs` | list(string) | `["us-east-1a","us-east-1b"]` | zonas de disponibilidade |
| `tiger_peer_cidr` | string | `"11.0.0.0/16"` | CIDR da Peering VPC do Tiger |
| `tiger_peering_connection_id` | string | `""` | `pcx-…` do pedido do Tiger (vazio até existir) |
| `db_port` | number | `5432` | porta do Postgres (doc do Tiger; endpoint público é 36101) |
| `project` / `environment` | string | `"serra-clara"` / `"demo"` | tags |

## Saídas (`outputs.tf`)

- `vpc_id`, `vpc_cidr`, `public_subnet_ids`, `private_subnet_ids`, `aws_account_id`,
  `db_security_group_id`, `peering_connection_state` (quando aplicável).

Estas saídas fornecem o **VPC ID** e o **account ID** que você informa no Tiger Console
para o Tiger emitir o pedido de peering.

## Estrutura de arquivos (`terraform/`)

```
versions.tf              # required_version + required_providers (aws ~> 5)
providers.tf             # provider aws (profile, region)
variables.tf             # variáveis acima
network.tf               # VPC, subnets, IGW, route tables e associações
peering.tf               # accepter + rotas + security group (gated por count)
outputs.tf               # saídas
terraform.tfvars.example # exemplo de valores (sem segredos)
README.md                # passos do lado Tiger + como validar/plan
```

## Passos manuais do lado Tiger (documentados no README)

1. No Tiger Console → `Security` > `VPC`, a Peering VPC já existe (`11.0.0.0/16`, us-east-1).
2. Em `VPC Peering` > `Add`: informar AWS account ID `<AWS_ACCOUNT_ID>`, o `vpc_id` (saída do
   Terraform), CIDR `10.20.0.0/16`, região `us-east-1`. O Tiger envia o pedido (`pcx-…`).
3. Preencher `tiger_peering_connection_id` com o `pcx-…` e `terraform apply` para aceitar
   e rotear (ou aceitar pelo Console AWS).
4. No Tiger Console, anexar o serviço `db-17829` à Peering VPC.

## Verificação

- `cd terraform && terraform fmt -check -recursive` — sem diffs.
- `terraform init -backend=false && terraform validate` — válido (sem credenciais).
- `terraform plan` (opcional, com `AWS_PROFILE=bianchi_aws`) — plano coerente; com
  `tiger_peering_connection_id` vazio, o plano cria apenas rede (sem os recursos de peering).
- CI existente (`.github/workflows/terraform.yml`) roda `fmt`/`validate` + Trivy.

## Fora de escopo (YAGNI)

- Computação para rodar o web-system na VPC (EC2/ECS/ACI) — o app hoje conecta ao Tiger
  pela internet pública; peering só passa a ser usado quando a computação estiver na VPC.
- NAT gateway, backend remoto de state, múltiplos ambientes.
- Automação dos passos do lado Tiger (feitos no Console).

## Nota de documentação

A arquitetura no `CLAUDE.md` cita "VPC Peering / Private Link" genericamente. Na prática:
o Tiger na AWS suporta **VPC peering** (adotado aqui) e **AWS PrivateLink**; na Azure é
**Private Link**. Atualizar o `CLAUDE.md` para refletir o mecanismo adotado (peering/AWS).
