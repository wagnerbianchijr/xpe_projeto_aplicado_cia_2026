# EC2 #2: web-system (dashboard) público em HTTPS/443 via Caddy (self-signed),
# reverse proxy para o uvicorn local. Roda dentro da VPC (alcança o Tiger pelo
# peering quando o serviço estiver anexado; senão pelo endpoint público).
# Ligado/desligado por var.web_enabled.

locals {
  web_count      = var.web_enabled ? 1 : 0
  web_name       = "${var.project}-web"
  web_src_bucket = "${var.project}-web-src-${data.aws_caller_identity.current.account_id}"
  web_src_key    = "websystem.zip"
}

# --- Código do web-system entregue via S3 ----------------------------------

data "archive_file" "web" {
  count       = local.web_count
  type        = "zip"
  output_path = "${path.module}/build/websystem.zip"
  source_dir  = "${path.module}/../web-system"
  excludes = [
    ".venv",
    ".venv/**",
    "__pycache__",
    "__pycache__/**",
    "**/__pycache__/**",
    ".pytest_cache",
    ".pytest_cache/**",
    "tests",
    "tests/**",
    ".env",
    ".env.example",
    "pytest.ini",
    "Dockerfile",
    ".dockerignore",
    "README.md",
  ]
}

resource "aws_s3_bucket" "web_src" {
  count         = local.web_count
  bucket        = local.web_src_bucket
  force_destroy = true
  tags          = { Name = local.web_src_bucket }
}

resource "aws_s3_bucket_public_access_block" "web_src" {
  count                   = local.web_count
  bucket                  = aws_s3_bucket.web_src[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "web" {
  count       = local.web_count
  bucket      = aws_s3_bucket.web_src[0].id
  key         = local.web_src_key
  source      = data.archive_file.web[0].output_path
  source_hash = data.archive_file.web[0].output_md5
}

# --- IAM: SSM Session Manager + leitura do segredo + download do código -----

resource "aws_iam_role" "web" {
  count              = local.web_count
  name               = "${local.web_name}-role"
  assume_role_policy = data.aws_iam_policy_document.plc_assume.json # mesmo trust (ec2)
  tags               = { Name = "${local.web_name}-role" }
}

resource "aws_iam_role_policy_attachment" "web_ssm_core" {
  count      = local.web_count
  role       = aws_iam_role.web[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "web_access" {
  count = local.web_count
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
    sid       = "DownloadWebCode"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.web_src[0].arn}/${local.web_src_key}"]
  }
}

resource "aws_iam_role_policy" "web_access" {
  count  = local.web_count
  name   = "${local.web_name}-access"
  role   = aws_iam_role.web[0].id
  policy = data.aws_iam_policy_document.web_access[0].json
}

resource "aws_iam_instance_profile" "web" {
  count = local.web_count
  name  = "${local.web_name}-profile"
  role  = aws_iam_role.web[0].name
}

# --- Security group: inbound 443 público + saída liberada -------------------

resource "aws_security_group" "web" {
  count       = local.web_count
  name        = "${local.web_name}-sg"
  description = "web-system: HTTPS publico (443) + saida."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS publico"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Toda saida (pip/SSM/Caddy e Tiger via peering ou publico)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.web_name}-sg" }
}

# --- Instância EC2 web-system -----------------------------------------------

resource "aws_instance" "web" {
  count                       = local.web_count
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.web_instance_type
  subnet_id                   = aws_subnet.public[0].id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.web[0].id]
  iam_instance_profile        = aws_iam_instance_profile.web[0].name

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    encrypted = true
  }

  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/templates/web_user_data.sh.tftpl", {
    bucket   = aws_s3_bucket.web_src[0].id
    key      = local.web_src_key
    region   = var.aws_region
    db_param = var.db_url_ssm_param
  })

  depends_on = [aws_s3_object.web]

  # AMI "latest" do AL2023: evita recriar a instância num apply de rotina quando
  # a Amazon publica uma nova AMI. Remova para atualizar a AMI de propósito.
  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = local.web_name }
}
