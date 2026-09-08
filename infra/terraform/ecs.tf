resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "service" {
  for_each = toset(["backend", "frontend", "github-mcp"])

  name              = "/ecs/${local.name}/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = "${local.name}.local"
  description = "Private service discovery for Clutch"
  vpc         = aws_vpc.main.id
}

resource "aws_service_discovery_service" "github_mcp" {
  name = "github-mcp"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {}
}

resource "aws_service_discovery_service" "backend" {
  name = "backend"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {}
}

resource "aws_lb" "app" {
  name               = substr(local.name, 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.enable_deletion_protection

  depends_on = [aws_budgets_budget.monthly]
}

resource "aws_lb_target_group" "frontend" {
  name        = substr("${local.name}-front", 0, 32)
  port        = 8501
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    path                = "/_stcore/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_target_group" "backend" {
  name        = substr("${local.name}-back", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  count = var.acm_certificate_arn == null ? 1 : 0

  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  count = var.acm_certificate_arn == null ? 0 : 1

  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  count = var.acm_certificate_arn == null ? 0 : 1

  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

locals {
  app_listener_arn = one(concat(aws_lb_listener.http[*].arn, aws_lb_listener.https[*].arn))
  app_scheme       = var.acm_certificate_arn == null ? "http" : "https"
}

resource "aws_lb_listener_rule" "backend" {
  listener_arn = local.app_listener_arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/health", "/interview*", "/progress*", "/review*", "/runtime*"]
    }
  }
}

locals {
  log_configuration = {
    logDriver = "awslogs"
    options = {
      awslogs-region        = var.aws_region
      awslogs-stream-prefix = "ecs"
    }
  }
  tracing_enabled = (
    var.langfuse_public_key_secret_arn != null &&
    var.langfuse_secret_key_secret_arn != null
  )
  backend_secrets = concat(
    [{
      name      = "CLUTCH_DB_PASSWORD"
      valueFrom = "${aws_db_instance.main.master_user_secret[0].secret_arn}:password::"
    }],
    var.clutch_api_key_secret_arn == null ? [] : [{
      name      = "CLUTCH_API_KEY"
      valueFrom = var.clutch_api_key_secret_arn
    }],
    var.openai_api_key_secret_arn == null ? [] : [{
      name      = "OPENAI_API_KEY"
      valueFrom = var.openai_api_key_secret_arn
    }],
    var.langfuse_public_key_secret_arn == null ? [] : [{
      name      = "LANGFUSE_PUBLIC_KEY"
      valueFrom = var.langfuse_public_key_secret_arn
    }],
    var.langfuse_secret_key_secret_arn == null ? [] : [{
      name      = "LANGFUSE_SECRET_KEY"
      valueFrom = var.langfuse_secret_key_secret_arn
    }],
  )
  github_mcp_secrets = var.github_token_secret_arn == null ? [] : [{
    name      = "GITHUB_TOKEN"
    valueFrom = var.github_token_secret_arn
  }]
  frontend_secrets = var.clutch_api_key_secret_arn == null ? [] : [{
    name      = "CLUTCH_API_KEY"
    valueFrom = var.clutch_api_key_secret_arn
  }]
}

resource "aws_ecs_task_definition" "github_mcp" {
  family                   = "${local.name}-github-mcp"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name      = "github-mcp"
    image     = "${aws_ecr_repository.service["github-mcp"].repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8001
      hostPort      = 8001
      protocol      = "tcp"
    }]
    environment = [
      { name = "CLUTCH_MCP_HOST", value = "0.0.0.0" },
      { name = "CLUTCH_MCP_TRANSPORT", value = "streamable-http" },
      {
        name  = "GITHUB_MCP_ALLOWED_HOSTS"
        value = "github-mcp.${aws_service_discovery_private_dns_namespace.main.name}:8001,127.0.0.1:8001,localhost:8001"
      },
    ]
    secrets = local.github_mcp_secrets
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2)\""]
      interval    = 30
      retries     = 3
      startPeriod = 15
      timeout     = 5
    }
    logConfiguration = merge(local.log_configuration, {
      options = merge(local.log_configuration.options, {
        awslogs-group = aws_cloudwatch_log_group.service["github-mcp"].name
      })
    })
  }])
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${aws_ecr_repository.service["backend"].repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "CLUTCH_MODEL_DAILY_USD", value = tostring(var.model_daily_usd) },
      { name = "CLUTCH_MODEL_PER_REQUEST_USD", value = tostring(var.model_per_request_usd) },
      { name = "CLUTCH_REQUIRE_AUTH", value = "true" },
      { name = "CLUTCH_DB_HOST", value = aws_db_instance.main.address },
      { name = "CLUTCH_DB_NAME", value = "clutch" },
      { name = "CLUTCH_DB_PORT", value = tostring(aws_db_instance.main.port) },
      { name = "CLUTCH_DB_USER", value = "clutch" },
      { name = "GITHUB_MCP_URL", value = "http://github-mcp.${aws_service_discovery_private_dns_namespace.main.name}:8001/mcp" },
      { name = "LANGFUSE_BASE_URL", value = var.langfuse_base_url },
      { name = "LANGFUSE_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED", value = "false" },
      { name = "LANGFUSE_TRACING_ENABLED", value = tostring(local.tracing_enabled) },
      { name = "OPENAI_EMBEDDING_MODEL", value = var.openai_embedding_model },
      { name = "OPENAI_MODEL", value = var.openai_model },
      { name = "REDIS_URL", value = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0" },
    ]
    secrets = local.backend_secrets
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)\""]
      interval    = 30
      retries     = 3
      startPeriod = 30
      timeout     = 5
    }
    logConfiguration = merge(local.log_configuration, {
      options = merge(local.log_configuration.options, {
        awslogs-group = aws_cloudwatch_log_group.service["backend"].name
      })
    })
  }])

  lifecycle {
    precondition {
      condition     = var.service_desired_count == 0 || var.clutch_api_key_secret_arn != null
      error_message = "clutch_api_key_secret_arn is required before starting public ECS services."
    }
  }
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${local.name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "${aws_ecr_repository.service["frontend"].repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8501
      hostPort      = 8501
      protocol      = "tcp"
    }]
    environment = [{
      name  = "CLUTCH_API_BASE_URL"
      value = "http://backend.${aws_service_discovery_private_dns_namespace.main.name}:8000"
    }]
    secrets = local.frontend_secrets
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2)\""]
      interval    = 30
      retries     = 3
      startPeriod = 30
      timeout     = 5
    }
    logConfiguration = merge(local.log_configuration, {
      options = merge(local.log_configuration.options, {
        awslogs-group = aws_cloudwatch_log_group.service["frontend"].name
      })
    })
  }])
}

resource "aws_ecs_service" "github_mcp" {
  name            = "github-mcp"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.github_mcp.arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    assign_public_ip = true
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.github_mcp.id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.github_mcp.arn
  }
}

resource "aws_ecs_service" "backend" {
  name            = "backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    assign_public_ip = true
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.backend.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  service_registries {
    registry_arn = aws_service_discovery_service.backend.arn
  }

  depends_on = [aws_lb_listener_rule.backend]
}

resource "aws_ecs_service" "frontend" {
  name            = "frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    assign_public_ip = true
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.frontend.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 8501
  }

  depends_on = [aws_lb_listener.http, aws_lb_listener.https]
}
