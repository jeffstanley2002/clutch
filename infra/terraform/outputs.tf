output "application_url" {
  description = "Public Clutch URL. Configure ACM to receive an HTTPS URL."
  value       = "${local.app_scheme}://${aws_lb.app.dns_name}"
}

output "ecr_repository_urls" {
  description = "Repositories to which CI publishes immutable images."
  value       = { for name, repository in aws_ecr_repository.service : name => repository.repository_url }
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "database_endpoint" {
  description = "Private RDS endpoint; password stays in the RDS-managed secret."
  value       = aws_db_instance.main.endpoint
}

output "redis_endpoint" {
  description = "Private TLS Redis endpoint."
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}
