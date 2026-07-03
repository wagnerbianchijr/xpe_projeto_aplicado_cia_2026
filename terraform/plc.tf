# EC2-PLC: instância que atua como o "PLC" da planta — roda o simulador IIoT
# (turnkey via user_data) e grava no Tiger Cloud. Subnet pública (internet para
# bootstrap), acesso via SSM Session Manager (sem chave SSH), segredo lido do
# SSM Parameter Store. Todo o bloco é ligado/desligado por var.plc_enabled.

locals {
  plc_count      = var.plc_enabled ? 1 : 0
  plc_name       = "${var.project}-plc"
  plc_src_bucket = "${var.project}-plc-src-${data.aws_caller_identity.current.account_id}"
  plc_src_key    = "simulador.zip"
  db_param_arn   = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.db_url_ssm_param}"
}

# AMI mais recente do Amazon Linux 2023 (via parâmetro público do SSM).
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

# --- Código do simulador entregue via S3 -----------------------------------

data "archive_file" "simulador" {
  count       = local.plc_count
  type        = "zip"
  output_path = "${path.module}/build/simulador.zip"

  dynamic "source" {
    for_each = toset(["main.py", "config.py", "catalog.py", "generator.py", "writer.py", "requirements.txt"])
    content {
      content  = file("${path.module}/../simulador/${source.value}")
      filename = source.value
    }
  }
}

resource "aws_s3_bucket" "plc_src" {
  count         = local.plc_count
  bucket        = local.plc_src_bucket
  force_destroy = true
  tags          = { Name = local.plc_src_bucket }
}

resource "aws_s3_bucket_public_access_block" "plc_src" {
  count                   = local.plc_count
  bucket                  = aws_s3_bucket.plc_src[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "simulador" {
  count       = local.plc_count
  bucket      = aws_s3_bucket.plc_src[0].id
  key         = local.plc_src_key
  source      = data.archive_file.simulador[0].output_path
  source_hash = data.archive_file.simulador[0].output_md5
}

# --- IAM: SSM Session Manager + leitura do segredo + download do código -----

data "aws_iam_policy_document" "plc_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "plc" {
  count              = local.plc_count
  name               = "${local.plc_name}-role"
  assume_role_policy = data.aws_iam_policy_document.plc_assume.json
  tags               = { Name = "${local.plc_name}-role" }
}

resource "aws_iam_role_policy_attachment" "plc_ssm_core" {
  count      = local.plc_count
  role       = aws_iam_role.plc[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "plc_access" {
  count = local.plc_count
  statement {
    sid       = "ReadDbUrlParam"
    actions   = ["ssm:GetParameter"]
    resources = [local.db_param_arn]
  }
  statement {
    sid       = "DecryptSsmSecureString"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }
  statement {
    sid       = "DownloadSimuladorCode"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.plc_src[0].arn}/${local.plc_src_key}"]
  }
}

resource "aws_iam_role_policy" "plc_access" {
  count  = local.plc_count
  name   = "${local.plc_name}-access"
  role   = aws_iam_role.plc[0].id
  policy = data.aws_iam_policy_document.plc_access[0].json
}

resource "aws_iam_instance_profile" "plc" {
  count = local.plc_count
  name  = "${local.plc_name}-profile"
  role  = aws_iam_role.plc[0].name
}

# --- Security group: só saída (pip + Tiger); SSM não precisa de entrada ------

resource "aws_security_group" "plc" {
  count       = local.plc_count
  name        = "${local.plc_name}-sg"
  description = "EC2-PLC: saida para internet (bootstrap) e Tiger."
  vpc_id      = aws_vpc.main.id

  egress {
    description = "Toda saida (pip/SSM/HTTPS e Tiger via peering ou publico)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.plc_name}-sg" }
}

# --- Instância EC2-PLC -------------------------------------------------------

resource "aws_instance" "plc" {
  count                       = local.plc_count
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.plc_instance_type
  subnet_id                   = aws_subnet.public[0].id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.plc[0].id]
  iam_instance_profile        = aws_iam_instance_profile.plc[0].name

  metadata_options {
    http_tokens   = "required" # IMDSv2 obrigatório
    http_endpoint = "enabled"
  }

  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/templates/plc_user_data.sh.tftpl", {
    bucket   = aws_s3_bucket.plc_src[0].id
    key      = local.plc_src_key
    region   = var.aws_region
    db_param = var.db_url_ssm_param
  })

  depends_on = [aws_s3_object.simulador]

  # A AMI vem do parâmetro "latest" do AL2023; sem isto, quando a Amazon publica
  # uma nova AMI, um apply de rotina recriaria a instância. Atualize a AMI de
  # propósito (removendo este ignore) quando quiser aplicar patches.
  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = local.plc_name }
}
