output "ecr_repository_urls" {
  description = "LocalStack ECR repository URLs for the three Clutch images."
  value       = { for name, repository in aws_ecr_repository.service : name => repository.repository_url }
}

output "ecs_cluster_name" {
  description = "LocalStack ECS cluster name."
  value       = var.enable_emulated_ecs ? aws_ecs_cluster.main[0].name : null
}

output "ecs_service_names" {
  description = "LocalStack ECS service names."
  value = var.enable_emulated_ecs ? {
    backend    = aws_ecs_service.backend[0].name
    frontend   = aws_ecs_service.frontend[0].name
    github_mcp = aws_ecs_service.github_mcp[0].name
  } : {}
}

output "clutch_api_key_secret_arn" {
  description = "LocalStack secret ARN used by backend and frontend task definitions."
  value       = aws_secretsmanager_secret.clutch_api_key.arn
}

output "emulated_ecs_enabled" {
  description = "Whether this apply attempted LocalStack ECS resources."
  value       = var.enable_emulated_ecs
}
