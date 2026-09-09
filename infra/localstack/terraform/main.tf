terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.57.1, < 7.0.0"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    apigateway             = local.localstack_endpoint
    applicationautoscaling = local.localstack_endpoint
    cloudformation         = local.localstack_endpoint
    cloudwatch             = local.localstack_endpoint
    ec2                    = local.localstack_endpoint
    ecr                    = local.localstack_endpoint
    ecs                    = local.localstack_endpoint
    elasticache            = local.localstack_endpoint
    elbv2                  = local.localstack_endpoint
    iam                    = local.localstack_endpoint
    logs                   = local.localstack_endpoint
    rds                    = local.localstack_endpoint
    route53                = local.localstack_endpoint
    s3                     = local.localstack_endpoint
    secretsmanager         = local.localstack_endpoint
    servicediscovery       = local.localstack_endpoint
    sts                    = local.localstack_endpoint
  }

  default_tags {
    tags = local.common_tags
  }
}

locals {
  localstack_endpoint = "http://localhost:4566"
  name                = "${var.project_name}-${var.environment}"
  service_names       = toset(["backend", "frontend", "github-mcp"])
  service_image_urls = var.enable_emulated_ecs ? {
    backend    = var.enable_emulated_ecr ? "${aws_ecr_repository.service["backend"].repository_url}:${var.image_tag}" : "clutch-backend:${var.image_tag}"
    frontend   = var.enable_emulated_ecr ? "${aws_ecr_repository.service["frontend"].repository_url}:${var.image_tag}" : "clutch-frontend:${var.image_tag}"
    github-mcp = var.enable_emulated_ecr ? "${aws_ecr_repository.service["github-mcp"].repository_url}:${var.image_tag}" : "clutch-github-mcp:${var.image_tag}"
  } : {}
  common_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
    Runtime     = "LocalStack"
  }
}

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

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy" "runtime_secrets" {
  name = "runtime-secrets"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetAuthorizationToken",
        "ecr:GetDownloadUrlForLayer",
      ]
      Resource = "*"
    }]
  })
}

resource "aws_secretsmanager_secret" "clutch_api_key" {
  name                    = "${local.name}/clutch-api-key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "clutch_api_key" {
  secret_id     = aws_secretsmanager_secret.clutch_api_key.id
  secret_string = var.clutch_api_key
}

resource "aws_ecr_repository" "service" {
  for_each = var.enable_emulated_ecr ? local.service_names : toset([])

  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_cloudwatch_log_group" "service" {
  for_each = local.service_names

  name              = "/ecs/${local.name}/${each.key}"
  retention_in_days = 1
}

resource "aws_ecs_cluster" "main" {
  count = var.enable_emulated_ecs ? 1 : 0

  name = local.name
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = local.name }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  availability_zone       = "${var.aws_region}a"
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 0)
  map_public_ip_on_launch = true

  tags = { Name = "${local.name}-public-1" }
}

resource "aws_security_group" "service" {
  name        = "${local.name}-service"
  description = "LocalStack ECS service security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Backend"
    from_port   = 8000
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "Streamlit"
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-service" }
}

locals {
  log_options = {
    awslogs-region        = var.aws_region
    awslogs-stream-prefix = "ecs"
  }
}

resource "aws_ecs_task_definition" "github_mcp" {
  count = var.enable_emulated_ecs ? 1 : 0

  family                   = "${local.name}-github-mcp"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "github-mcp"
    image     = local.service_image_urls["github-mcp"]
    essential = true
    portMappings = [{
      containerPort = 8001
      hostPort      = 8001
      protocol      = "tcp"
    }]
    environment = [
      { name = "CLUTCH_MCP_HOST", value = "0.0.0.0" },
      { name = "CLUTCH_MCP_TRANSPORT", value = "streamable-http" },
      { name = "GITHUB_MCP_ALLOWED_HOSTS", value = "127.0.0.1:8001,localhost:8001,github-mcp:8001" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = merge(local.log_options, {
        awslogs-group = aws_cloudwatch_log_group.service["github-mcp"].name
      })
    }
  }])
}

resource "aws_ecs_task_definition" "backend" {
  count = var.enable_emulated_ecs ? 1 : 0

  family                   = "${local.name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = local.service_image_urls["backend"]
    essential = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "CLUTCH_REQUIRE_AUTH", value = "true" },
      { name = "CLUTCH_MODEL_DAILY_USD", value = "1.00" },
      { name = "CLUTCH_MODEL_PER_REQUEST_USD", value = "0.10" },
      { name = "DATABASE_URL", value = "postgresql+asyncpg://clutch:clutch-local@postgres:5432/clutch" },
      { name = "GITHUB_MCP_URL", value = "http://github-mcp:8001/mcp" },
      { name = "OPENAI_MODEL", value = var.openai_model },
      { name = "REDIS_URL", value = "redis://redis:6379/0" },
    ]
    secrets = [{
      name      = "CLUTCH_API_KEY"
      valueFrom = aws_secretsmanager_secret.clutch_api_key.arn
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = merge(local.log_options, {
        awslogs-group = aws_cloudwatch_log_group.service["backend"].name
      })
    }
  }])
}

resource "aws_ecs_task_definition" "frontend" {
  count = var.enable_emulated_ecs ? 1 : 0

  family                   = "${local.name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = local.service_image_urls["frontend"]
    essential = true
    portMappings = [{
      containerPort = 8501
      hostPort      = 8501
      protocol      = "tcp"
    }]
    environment = [{
      name  = "CLUTCH_API_BASE_URL"
      value = "http://backend:8000"
    }]
    secrets = [{
      name      = "CLUTCH_API_KEY"
      valueFrom = aws_secretsmanager_secret.clutch_api_key.arn
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = merge(local.log_options, {
        awslogs-group = aws_cloudwatch_log_group.service["frontend"].name
      })
    }
  }])
}

resource "aws_ecs_service" "github_mcp" {
  count = var.enable_emulated_ecs ? 1 : 0

  name            = "github-mcp"
  cluster         = aws_ecs_cluster.main[0].id
  task_definition = aws_ecs_task_definition.github_mcp[0].arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    security_groups  = [aws_security_group.service.id]
    subnets          = [aws_subnet.public.id]
  }
}

resource "aws_ecs_service" "backend" {
  count = var.enable_emulated_ecs ? 1 : 0

  name            = "backend"
  cluster         = aws_ecs_cluster.main[0].id
  task_definition = aws_ecs_task_definition.backend[0].arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    security_groups  = [aws_security_group.service.id]
    subnets          = [aws_subnet.public.id]
  }
}

resource "aws_ecs_service" "frontend" {
  count = var.enable_emulated_ecs ? 1 : 0

  name            = "frontend"
  cluster         = aws_ecs_cluster.main[0].id
  task_definition = aws_ecs_task_definition.frontend[0].arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    security_groups  = [aws_security_group.service.id]
    subnets          = [aws_subnet.public.id]
  }
}
