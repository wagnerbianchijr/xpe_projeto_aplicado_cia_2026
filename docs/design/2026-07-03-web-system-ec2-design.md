# EC2 #2 — web-system público (443) — Design

Segundo EC2 na VPC AWS que roda o **web-system** (dashboard) e o serve em **HTTPS/443**
publicamente. Complementa o EC2-PLC (que roda o simulador). Extensão do componente
`terraform`.

## Contexto

- VPC `vpc-094a97e0987147591` (`10.20.0.0/16`), subnets públicas/privadas, peering ao
  Tiger já provisionados.
- EC2-PLC já existe (`plc.tf`) com o padrão S3 (código) + SSM Parameter Store (segredo)
  + SSM Session Manager (acesso). Este design reusa esse padrão.
- Serviço Tiger `db-17829` (`x5mgo2i0fb`), us-east-1. `DATABASE_URL` no SSM Parameter
  Store `/serra-clara/plc/database_url` (SecureString).

## Componente

- **EC2:** `t3.micro`, Amazon Linux 2023, **subnet pública** com IP público, IMDSv2
  obrigatório. Acesso por **SSM Session Manager** (sem chave SSH).
- **Serviço web (443):** **Caddy** como reverse proxy com `tls internal` (CA interna do
  Caddy → cert self-signed) escutando em **443** e encaminhando para o **uvicorn** local
  (`127.0.0.1:8000`). Acesso pelo IP público; o navegador avisa cert não confiável.
- **Security group `web`:** **inbound TCP 443** de `0.0.0.0/0`; egress liberado. Único SG
  do ambiente com regra de entrada.
- **Código:** o Terraform zipa `../web-system` (app + `templates/` + `static/`, excluindo
  `.venv`, `__pycache__`, `.pytest_cache`, `tests`, `.env*`) e envia a um bucket S3
  dedicado (`serra-clara-web-src-<account_id>`, com Public Access Block). O user_data
  baixa do S3.
- **Bootstrap (user_data):** instala Python 3.11 (AL2023 default é 3.9; o código usa
  anotações `X | None`, PEP 604) + Caddy (binário oficial). Cria venv + `pip install`.
  Lê `DATABASE_URL` do SSM → escreve `.env` (com `HOST=127.0.0.1`, `PORT=8000`). Sobe
  `websystem.service` (uvicorn) e `caddy.service` (443) via systemd.
- **IAM:** role com `AmazonSSMManagedInstanceCore` + `ssm:GetParameter` no parâmetro do
  DB + `kms:Decrypt` (via `kms:ViaService=ssm`) + `s3:GetObject` do zip do web.
- **Gating:** `var.web_enabled` (default `true`), independente do PLC.

## Arquivos

- `web.tf` — EC2, SG, IAM, S3 (bucket/PAB/archive/object), user_data.
- `templates/web_user_data.sh.tftpl` — bootstrap.
- `variables.tf` (+ `web_enabled`, `web_instance_type`), `outputs.tf`
  (+ `web_instance_id`, `web_public_ip`, `web_url`, `web_ssm_start_command`).
- `terraform/README.md` atualizado.

## Conexão ao banco

Usa o mesmo `DATABASE_URL` do SSM. Hoje aponta ao endpoint público (`36101`) — funciona
de imediato. Ao **anexar o serviço à Peering VPC** (Tiger Console), o banco vira privado:
atualizar o parâmetro SSM (porta provável `5432`) e reiniciar os serviços nos dois EC2s;
ambos passam a usar o **peering**. O web-system do notebook deixaria de conectar (esperado).

## Verificação

- `terraform fmt`/`validate` limpos; `plan` coerente.
- Pós-apply: instância `running`, SSM `Online`; `curl -k https://<web_public_ip>/` → 200;
  KPIs renderizando com dados do PLC.

## Fora de escopo (YAGNI)

- Domínio/Let's Encrypt/ACM/ALB (usa self-signed).
- Redirect 80→443 (só 443).
- Autoscaling, múltiplas AZs para o web (uma instância).
