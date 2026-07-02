# terraform

Infraestrutura de rede na **AWS** para a solução IIoT da **Serra Clara Bebidas S.A.**,
com conexão privada ao serviço Tiger Cloud (**db-17829**, `us-east-1`) via **VPC peering**.

Entrega **demonstrativa**: o código passa em `fmt` + `validate` (e `plan` com
credenciais). O `apply` é opcional.

## O que é provisionado

- **VPC** `10.20.0.0/16` (não colide com a Peering VPC do Tiger `11.0.0.0/16`).
- **Subnets** públicas (`10.20.0.0/24`, `10.20.1.0/24`) e privadas (`10.20.10.0/24`,
  `10.20.11.0/24`) em `us-east-1a`/`us-east-1b`.
- **Internet Gateway** + route table pública. Route table privada sem NAT.
- **VPC peering** ao Tiger (parametrizado): accepter + rotas para `11.0.0.0/16` +
  security group de saída na porta do Postgres. Criados apenas quando
  `tiger_peering_connection_id` está preenchido.

Arquivos: `versions.tf`, `providers.tf`, `variables.tf`, `network.tf`, `peering.tf`,
`outputs.tf`.

## Pré-requisitos

- Terraform >= 1.9.
- Perfil da AWS CLI `bianchi_aws` (região `us-east-1`) — só necessário para `plan`/`apply`.
- Serviço Tiger Cloud em `us-east-1` e a Peering VPC criada no Tiger Console
  (`11.0.0.0/16`).

## Validar (sem credenciais)

```bash
cd terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

## Plan / Apply (com credenciais)

```bash
export AWS_PROFILE=bianchi_aws
terraform init
terraform plan
# terraform apply   # cria a rede; peering só entra quando o pcx-... é informado
```

Com `tiger_peering_connection_id` vazio, o plano cria **apenas a rede**.

## Configurar o VPC peering com o Tiger

O **Tiger inicia** o pedido; a **AWS aceita**.

1. `terraform apply` para criar a VPC. Anote as saídas `aws_account_id` e `vpc_id`.
2. No **Tiger Console** → `Security` > `VPC` (a Peering VPC `11.0.0.0/16` já existe) →
   coluna `VPC Peering` > `Add`: informe o **AWS account ID**, o **VPC ID**, o CIDR
   `10.20.0.0/16` e a região `us-east-1`. O Tiger envia o pedido de peering.
3. Copie o `pcx-...` que aparece na AWS, preencha `tiger_peering_connection_id`
   (em `terraform.tfvars`) e rode `terraform apply` para **aceitar** e **rotear**.
4. No Tiger Console, anexe o serviço `db-17829` à Peering VPC.
5. A partir de uma instância dentro desta VPC, conecte ao serviço usando a connection
   string do Tiger.

Referência: Tiger Cloud — *VPC Peering (AWS)*
(<https://www.tigerdata.com/docs/deploy/tiger-cloud/tiger-cloud-aws/security/vpc>).

## Variáveis principais

| Variável | Default | Uso |
|---|---|---|
| `aws_profile` | `bianchi_aws` | perfil da AWS CLI |
| `aws_region` | `us-east-1` | região (casa com o serviço Tiger) |
| `vpc_cidr` | `10.20.0.0/16` | CIDR da VPC |
| `tiger_peer_cidr` | `11.0.0.0/16` | CIDR da Peering VPC do Tiger |
| `tiger_peering_connection_id` | `""` | `pcx-...` do pedido do Tiger (vazio = sem peering) |
| `db_port` | `5432` | porta liberada ao Tiger (endpoint público usa 36101) |

Veja `terraform.tfvars.example` para um ponto de partida.

## Saídas

`aws_account_id`, `vpc_id`, `vpc_cidr`, `public_subnet_ids`, `private_subnet_ids`,
`db_security_group_id`, `peering_connection_state`.

## EC2-PLC (simulador na nuvem)

Uma instância EC2 atua como o **PLC** da planta: roda o simulador IIoT como serviço
e grava no Tiger. Ligada/desligada por `plc_enabled` (default `true`).

- `t3.micro`, Amazon Linux 2023, subnet pública, IMDSv2 obrigatório.
- Acesso via **SSM Session Manager** (sem chave SSH).
- **Pré-requisito (fora do Terraform):** o `DATABASE_URL` precisa existir no SSM
  Parameter Store como SecureString:

  ```bash
  aws ssm put-parameter --region us-east-1 --type SecureString --overwrite \
    --name /serra-clara/plc/database_url \
    --value "postgresql://USER:PASS@HOST:PORT/tsdb?sslmode=require"
  ```

- No boot, o `user_data`: instala **Python 3.11** (o padrão do AL2023 é 3.9, e o
  simulador usa anotações `X | None` que exigem 3.10+), baixa o código do simulador
  do S3, cria venv + `pip install`, lê o `DATABASE_URL` do SSM e sobe o `plc.service`
  (systemd) que roda `main.py`.
- Código do simulador é entregue via S3 (o Terraform zipa `../simulador` e faz upload).

Abrir sessão no PLC (saída `plc_ssm_start_command`):

```bash
aws ssm start-session --target <plc_instance_id> --region us-east-1 --profile bianchi_aws
# na instância: systemctl status plc ; journalctl -u plc -f
```

## Notas

- **Sem NAT gateway** (evita custo); o acesso ao Tiger é privado via peering.
- O **EC2-PLC** roda dentro desta VPC e grava no Tiger; o web-system continua
  conectando ao Tiger pela internet pública (fora da VPC).
- State local (sem backend remoto), adequado à entrega demonstrativa.
