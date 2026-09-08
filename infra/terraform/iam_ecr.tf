data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

locals {
  optional_secret_arns = compact([
    var.clutch_api_key_secret_arn,
    var.openai_api_key_secret_arn,
    var.github_token_secret_arn,
    var.langfuse_public_key_secret_arn,
    var.langfuse_secret_key_secret_arn,
  ])
  runtime_secret_arns = concat(
    [aws_db_instance.main.master_user_secret[0].secret_arn],
    local.optional_secret_arns,
  )
}

data "aws_iam_policy_document" "runtime_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = local.runtime_secret_arns
  }
}

resource "aws_iam_role_policy" "runtime_secrets" {
  name   = "runtime-secrets"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.runtime_secrets.json
}

resource "aws_ecr_repository" "service" {
  for_each = toset(["backend", "frontend", "github-mcp"])

  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "service" {
  for_each = aws_ecr_repository.service

  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain the newest 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}
